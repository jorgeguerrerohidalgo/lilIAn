"""Cliente SPARQL para el endpoint de datos abiertos de la BCN Chile.

Endpoint público: https://datos.bcn.cl/sparql (Virtuoso).

Tres tipos de queries:

1. ``query_norms()``  → lista de todas las normas con metadatos
   (bcn_id, tipo, número, título, fecha publicación, organismo).
   Devuelve hasta ~6.000 normas. Cacheable 24h.

2. ``query_norm_versions(bcn_id)`` → versiones históricas de una norma
   con su rango temporal (valid_from, valid_until). Permite saber qué
   versión estaba vigente en cualquier fecha.

3. ``query_norm_relations(bcn_id)`` → relaciones ``bcnnorms:modifica``,
   ``bcnnorms:deroga``, ``bcnnorms:rectifica``, ``bcnnorms:refunde``.
   Alimenta ``norm_relations``.

Rate limiting: 1 req/seg (configurable). Cache local en
``apps/backend/.cache/bcn/`` con TTL configurable. Reintentos
exponenciales en errores 5xx.

La BCN publica todo bajo Creative Commons con atribución. La URL
canónica de cada norma queda registrada en ``norm_catalog.url_bcn``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("lilian.bcn_client")

# BCN Open Data endpoints.
BCN_SPARQL_ENDPOINT = "https://datos.bcn.cl/sparql"
BCN_NAVEGAR_BASE = "https://www.bcn.cl/leychile/navegar?idNorma={bcn_id}"

# Default namespace prefixes we use in our SPARQL queries. BCN uses
# the ``bcnnorms`` ontology for norms.
BCN_NORMS_PREFIX = "http://datos.bcn.cl/ontologies/bcn-norms#"
BCN_DC_PREFIX = "http://purl.org/dc/elements/1.1/"
BCN_RDFS_PREFIX = "http://www.w3.org/2000/01/rdf-schema#"
BCN_OWL_PREFIX = "http://www.w3.org/2002/07/owl#"

# Rate limiting.
DEFAULT_MIN_INTERVAL_SECONDS = 1.0  # 1 req/sec — be polite to BCN
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0

# Cache.
DEFAULT_CACHE_DIR = Path(__file__).parent / ".cache" / "bcn"
DEFAULT_CACHE_TTL = timedelta(hours=24)


class BCNClientError(Exception):
    """Raised on any non-retryable BCN client error."""


class BCNClient:
    """Thin SPARQL/HTTP client for the BCN Open Data endpoint.

    Constructor params let you override the endpoint, rate limits and
    cache for tests (point at a local httpx mock or a fake cache dir).

    Usage::

        client = BCNClient()
        for norm in client.query_norms():
            print(norm["bcn_id"], norm["titulo"])

        versions = client.query_norm_versions("1984")
        rels = client.query_norm_relations("1984")
    """

    def __init__(
        self,
        endpoint: str = BCN_SPARQL_ENDPOINT,
        *,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        cache_dir: Optional[Path] = DEFAULT_CACHE_DIR,
        cache_ttl: timedelta = DEFAULT_CACHE_TTL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self.min_interval = min_interval_seconds
        self.max_retries = max_retries
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_ttl = cache_ttl
        self.timeout = timeout_seconds
        self._last_request_at: Optional[float] = None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query_norms(self, *, limit: Optional[int] = None) -> list[dict]:
        """Fetch the BCN catalog: every norm with its core metadata.

        The result is a list of dicts with at least:
            bcn_id, tipo, numero, titulo, fecha_publicacion,
            organismo_emisor, url_bcn, estado.

        When ``limit`` is None we page through all norms (~6.000 in
        total for BCN's current dataset). Results are cached to
        ``cache_dir/norms.json`` because the catalog rarely changes.
        """
        cache_key = f"norms_{limit or 'all'}"
        cached = self._read_cache(cache_key)
        if cached is not None:
            logger.info("cache hit for %s (%d norms)", cache_key, len(cached))
            return cached

        sparql = """
PREFIX bcnnorms: <http://datos.bcn.cl/ontologies/bcn-norms#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?norma ?tipo ?numero ?titulo ?fecha ?organismo ?estado
WHERE {
  ?norma a bcnnorms:Norm .
  ?norma dc:title ?titulo .
  OPTIONAL { ?norma bcnnorms:tipoNorma ?tipo }
  OPTIONAL { ?norma bcnnorms:numero ?numero }
  OPTIONAL { ?norma bcnnorms:fechaPublicacion ?fecha }
  OPTIONAL { ?norma bcnnorms:organismoEmisor ?organismo }
  OPTIONAL { ?norma bcnnorms:estado ?estado }
  FILTER (lang(?titulo) = "" || lang(?titulo) = "es")
}
ORDER BY ?titulo
"""
        rows = self._query_paginated(sparql, limit=limit)
        norms = [self._row_to_norm(r) for r in rows]
        self._write_cache(cache_key, norms)
        logger.info("fetched %d norms from BCN", len(norms))
        return norms

    def query_norm_versions(self, bcn_id: str) -> list[dict]:
        """Fetch the historical versions of a single norm.

        Returns a list of dicts:
            version_label, valid_from, valid_until, source_url, is_current

        ``is_current`` is heuristically set to ``True`` when
        ``valid_until`` is absent — BCN doesn't always expose this
        explicitly.
        """
        cache_key = f"versions_{bcn_id}"
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        sparql = f"""
PREFIX bcnnorms: <http://datos.bcn.cl/ontologies/bcn-norms#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>

SELECT DISTINCT ?version ?label ?valid_from ?valid_until ?url
WHERE {{
  ?norma dc:identifier "{bcn_id}" .
  ?version bcnnorms:versionDe ?norma .
  ?version dc:title ?label .
  OPTIONAL {{ ?version bcnnorms:fechaInicioVigencia ?valid_from }}
  OPTIONAL {{ ?version bcnnorms:fechaFinVigencia ?valid_until }}
  OPTIONAL {{ ?version dc:identifier ?url }}
}}
ORDER BY DESC(?valid_from)
"""
        rows = self._query(sparql)
        versions = [
            {
                "version_label": str(r.get("label") or ""),
                "valid_from": self._parse_date(r.get("valid_from")),
                "valid_until": self._parse_date(r.get("valid_until")),
                "source_url": str(r.get("url") or ""),
                "is_current": r.get("valid_until") is None,
            }
            for r in rows
        ]
        self._write_cache(cache_key, versions)
        return versions

    def query_norm_relations(self, bcn_id: str) -> list[dict]:
        """Fetch outgoing edges from a norm (what it modifies, deroga, etc.).

        Returns a list of dicts:
            relation_type (str), to_norm_bcn_id, article_ref, confidence
        """
        cache_key = f"relations_{bcn_id}"
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        sparql = f"""
PREFIX bcnnorms: <http://datos.bcn.cl/ontologies/bcn-norms#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>

SELECT DISTINCT ?rel ?target ?target_id ?article_ref
WHERE {{
  ?source dc:identifier "{bcn_id}" .
  VALUES ?rel {{ bcnnorms:modifica bcnnorms:deroga bcnnorms:rectifica bcnnorms:refunde bcnnorms:prorroga bcnnorms:reglamenta }}
  ?source ?rel ?target .
  OPTIONAL {{ ?target dc:identifier ?target_id }}
  OPTIONAL {{ ?target bcnnorms:articuloReferencia ?article_ref }}
}}
"""
        rows = self._query(sparql)
        relations = []
        rel_map = {
            str(self._ns("bcnnorms:modifica")): "modifica",
            str(self._ns("bcnnorms:deroga")): "deroga",
            str(self._ns("bcnnorms:rectifica")): "rectifica",
            str(self._ns("bcnnorms:refunde")): "refunde",
            str(self._ns("bcnnorms:prorroga")): "prorroga",
            str(self._ns("bcnnorms:reglamenta")): "reglamenta",
        }
        for r in rows:
            rel_uri = r.get("rel")
            rel_type = rel_map.get(rel_uri)
            if not rel_type:
                continue
            relations.append({
                "relation_type": rel_type,
                "to_norm_bcn_id": str(r.get("target_id") or ""),
                "article_ref": r.get("article_ref") or None,
                "confidence": 1.0,
            })
        self._write_cache(cache_key, relations)
        return relations

    def fetch_norm_html(self, bcn_id: str, *, force: bool = False) -> Optional[str]:
        """Fetch the BCN HTML page for a norm (the user-navigable view).

        Returns None when BCN returns the SPA shell without the actual
        text (very common — the site is a captcha-protected Angular
        SPA). The caller should fall back to local files in that case.
        Caches per-bcn_id with a 7-day TTL because the page rarely
        changes.
        """
        cache_key = f"html_{bcn_id}"
        cached = self._read_cache(cache_key, ttl=timedelta(days=7))
        if cached is not None and not force:
            return cached

        url = BCN_NAVEGAR_BASE.format(bcn_id=bcn_id)
        html = self._http_get_text(url)
        if html is None:
            return None
        # BCN returns the SPA shell when captcha blocks us. We detect
        # this by looking for the recaptcha script tag — if present,
        # the page is useless for ingestion.
        if "recaptcha/enterprise.js" in html or "Este proceso demora demasiado" in html:
            logger.warning("BCN returned SPA shell for %s — captcha gate", bcn_id)
            return None
        self._write_cache(cache_key, html)
        return html

    # ------------------------------------------------------------------
    # Query + cache plumbing
    # ------------------------------------------------------------------

    def _query(self, sparql: str) -> list[dict]:
        """Run a single SPARQL SELECT and return rows as dicts."""
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                r = httpx.post(
                    self.endpoint,
                    data={"query": sparql},
                    headers={
                        "Accept": "application/sparql-results+json",
                        "User-Agent": "lilian-corpus/1.0 (+legal-chile)",
                    },
                    timeout=self.timeout,
                )
                if r.status_code == 200:
                    return r.json().get("results", {}).get("bindings", [])
                if r.status_code in (429, 500, 502, 503, 504):
                    self._backoff(attempt)
                    continue
                raise BCNClientError(f"BCN SPARQL returned {r.status_code}: {r.text[:200]}")
            except httpx.HTTPError as exc:
                logger.warning("SPARQL request failed (attempt %d): %s", attempt + 1, exc)
                self._backoff(attempt)
        raise BCNClientError(f"SPARQL query failed after {self.max_retries} retries")

    def _query_paginated(self, sparql: str, *, limit: Optional[int]) -> list[dict]:
        """Run a SELECT and page through OFFSET/LIMIT to collect all rows.

        BCN's Virtuoso endpoint accepts standard OFFSET/LIMIT for
        queries < ~100k rows, which is enough for the ~6.000 norms
        catalog.
        """
        page_size = 500
        all_rows: list[dict] = []
        offset = 0
        while True:
            chunk_query = sparql + (f"\nLIMIT {page_size} OFFSET {offset}" if limit is None else f"\nLIMIT {limit}")
            rows = self._query(chunk_query)
            all_rows.extend(rows)
            if limit is not None or len(rows) < page_size:
                break
            offset += page_size
            if offset > 50000:  # safety stop — catalog is ~6k
                break
        return all_rows

    def _http_get_text(self, url: str) -> Optional[str]:
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                r = httpx.get(
                    url,
                    headers={
                        "User-Agent": "lilian-corpus/1.0 (+legal-chile)",
                        "Accept": "text/html,application/xhtml+xml",
                    },
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                if r.status_code == 200:
                    return r.text
                if r.status_code in (429, 500, 502, 503, 504):
                    self._backoff(attempt)
                    continue
                logger.warning("GET %s returned %d", url, r.status_code)
                return None
            except httpx.HTTPError as exc:
                logger.warning("GET %s failed (attempt %d): %s", url, attempt + 1, exc)
                self._backoff(attempt)
        return None

    def _throttle(self) -> None:
        """Sleep enough to respect self.min_interval between requests."""
        if self._last_request_at is None:
            self._last_request_at = time.monotonic()
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _backoff(self, attempt: int) -> None:
        delay = DEFAULT_RETRY_BACKOFF_SECONDS ** attempt
        logger.info("retrying in %.1fs (attempt %d)", delay, attempt + 1)
        time.sleep(delay)

    def _ns(self, suffix: str) -> str:
        """Resolve a prefixed name like ``bcnnorms:Norm`` to its full URI."""
        prefix, _, local = suffix.partition(":")
        table = {
            "bcnnorms": BCN_NORMS_PREFIX,
            "dc": BCN_DC_PREFIX,
            "rdfs": BCN_RDFS_PREFIX,
            "owl": BCN_OWL_PREFIX,
        }
        return f"{table[prefix]}{local}"

    def _row_to_norm(self, row: dict) -> dict:
        """Map a SPARQL JSON row to a flat dict for ``norm_catalog``."""
        bcn_id = self._extract_id(str(row.get("norma", {}).get("value", "")))
        titulo = str(row.get("titulo", {}).get("value", "")).strip()
        tipo = str(row.get("tipo", {}).get("value", "otro")).strip().lower() or "otro"
        numero = row.get("numero", {}).get("value")
        fecha = row.get("fecha", {}).get("value")
        organismo = row.get("organismo", {}).get("value")
        estado = row.get("estado", {}).get("value") if row.get("estado") else None
        return {
            "bcn_id": bcn_id,
            "tipo": tipo,
            "numero": numero,
            "titulo": titulo,
            "fecha_publicacion": self._parse_date(fecha),
            "organismo_emisor": organismo,
            "estado": (estado or "vigente").lower(),
            "url_bcn": BCN_NAVEGAR_BASE.format(bcn_id=bcn_id) if bcn_id else None,
        }

    @staticmethod
    def _extract_id(uri: str) -> str:
        """``http://datos.bcn.cl/recurso/<id>`` → ``<id>``."""
        if not uri:
            return ""
        return uri.rstrip("/").rsplit("/", 1)[-1]

    @staticmethod
    def _parse_date(value) -> Optional[str]:
        """ISO-8601 / XSD date → ``YYYY-MM-DD`` string. Returns None on failure."""
        if not value:
            return None
        s = str(value)
        # Accept "YYYY-MM-DD", "YYYY-MM-DDTHH:MM:SS", "YYYY-MM-DDZ", etc.
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y/%m/%d"):
            try:
                return datetime.strptime(s[:19].rstrip("Z"), fmt[:19 - len(fmt) + len("%Y-%m-%d")]).strftime("%Y-%m-%d")
            except ValueError:
                continue
        # Last resort: take the first 10 chars if they look like a date.
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]
        return None

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_path(self, key: str) -> Optional[Path]:
        if not self.cache_dir:
            return None
        safe = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"{safe}.json"

    def _read_cache(self, key: str, *, ttl: Optional[timedelta] = None) -> Optional[object]:
        path = self._cache_path(key)
        if not path or not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(payload["_fetched_at"])
            cache_ttl = ttl or self.cache_ttl
            if datetime.utcnow() - fetched_at > cache_ttl:
                return None
            return payload.get("data")
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _write_cache(self, key: str, data: object) -> None:
        path = self._cache_path(key)
        if not path:
            return
        payload = {
            "_fetched_at": datetime.utcnow().isoformat(),
            "data": _jsonable(data),
        }
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
        except OSError as exc:  # pragma: no cover - cache is best-effort
            logger.warning("cache write failed for %s: %s", key, exc)


def _jsonable(obj):
    """Convert SPARQL-JSON bindings to a JSON-serialisable shape."""
    if isinstance(obj, dict) and "value" in obj:
        return obj["value"]
    if isinstance(obj, list):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    return obj
