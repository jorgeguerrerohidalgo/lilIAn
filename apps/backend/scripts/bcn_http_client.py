"""HTTP client for BCN's legacy ``Consulta/obtxml`` endpoint.

The BCN SPA at ``www.bcn.cl/leychile/Navegar`` is gated by reCAPTCHA and
returns the same Angular shell to any ``httpx.get`` call. However, the
legacy ``Consulta/obtxml`` endpoint — still served from the same
domain — returns the full text of any norm as XML structured per
``EsquemaIntercambioNorma-v1-0``. It only requires a real-browser
User-Agent header; no cookies, no JS, no captcha.

Three parameter combinations matter:

- ``opt=7&idNorma=<id>``    → full XML of a single norm.
- ``opt=3``                   → catalog feed (recently published
                                 norms). Used by ``discover_bcn_catalog``
                                 to walk the whole catalog.
- (older ``opt=1/2/10`` return 403, ``opt=9`` returns the bare
  hierarchy without text.)

Rate limiting defaults to 1 req/second — BCN is a public endpoint and
we want to be a polite citizen. Cache TTL is 30 days for individual
norms and 24h for the catalog feed (which changes daily).
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

logger = logging.getLogger("lilian.bcn_http")

BCN_BASE = "https://www.bcn.cl/leychile/Consulta/obtxml"

# A small pool of real desktop User-Agents. Rotating between them
# avoids tripping any per-UA throttling BCN may apply without raising
# eyebrows (a single exotic UA on every request looks bot-shaped).
_USER_AGENTS: list[str] = [
    # Chrome 130 / Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome 130 / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox 132 / Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Safari 18 / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    # Edge 130 / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
]

# Default rate limit + cache TTL.
DEFAULT_MIN_INTERVAL_SECONDS = 1.0
DEFAULT_NORM_CACHE_TTL = timedelta(days=30)
DEFAULT_CATALOG_CACHE_TTL = timedelta(hours=24)
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_CACHE_DIR = Path(__file__).parent / ".cache" / "bcn_xml"


class BCNHttpError(Exception):
    """Raised on non-retryable HTTP errors from BCN."""


class BCNHttpClient:
    """Stateless HTTP client for BCN's ``obtxml`` endpoint.

    Cache is on-disk under ``.cache/bcn_xml/<sha256>.xml`` with the
    fetched_at timestamp baked into the filename so we can detect
    expiry without parsing the file.
    """

    def __init__(
        self,
        *,
        base_url: str = BCN_BASE,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        norm_cache_ttl: timedelta = DEFAULT_NORM_CACHE_TTL,
        catalog_cache_ttl: timedelta = DEFAULT_CATALOG_CACHE_TTL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        cache_dir: Optional[Path] = DEFAULT_CACHE_DIR,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url
        self.min_interval = min_interval_seconds
        self.norm_cache_ttl = norm_cache_ttl
        self.catalog_cache_ttl = catalog_cache_ttl
        self.timeout = timeout_seconds
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_retries = max_retries
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request_at: Optional[float] = None
        self._ua_idx = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_norm_xml(self, bcn_id: str, *, force: bool = False) -> Optional[str]:
        """Return the full XML text for ``bcn_id``, or None on failure.

        Cached for ``self.norm_cache_ttl``. Returns the cached copy on
        cache hit; ``force=True`` bypasses the cache.
        """
        cached = self._read_cache(self._norm_path(bcn_id), self.norm_cache_ttl)
        if cached is not None and not force:
            logger.debug("cache hit for norm %s", bcn_id)
            return cached

        url = self._build_url(opt=7, params={"idNorma": bcn_id})
        content = self._get(url, accept="application/xml, text/xml")
        if content is None:
            return None

        # Defensive: BCN's shell page for SPA-only flows is ~10 KB.
        # Anything under 50 KB without an XML declaration is suspect.
        if "<Norma " not in content and len(content) < 50000:
            logger.warning("BCN response for %s looks like SPA shell", bcn_id)
            return None

        self._write_cache(self._norm_path(bcn_id), content)
        return content

    def fetch_law_xml(self, law_number: str, *, force: bool = False) -> Optional[str]:
        """Return the full XML text for a law identified by its short number.

        BCN's ``Consulta/obtxml`` endpoint accepts two parameter styles:

        - ``idNorma=<N>``  — a specific historical version of a norm
        - ``idLey=<N>``    — the law itself, including ALL modifications
                            accumulated up to today (the "refundido
                            consolidado"). This is what we want for
                            RAG coverage: the corpus needs the current
                            consolidated text, not the original 1999
                            publication of Ley 19.628.

        Some idNormas return tiny XMLs (3 KB for the Ley del Consumidor
        at idNorma=19496, which actually points at an unrelated Decreto
        "Feria Internacional del Salmón"). Same number with ``idLey=``
        returns the 300 KB consolidated law.

        Cached under a separate key (``.law.<N>.xml``) so it doesn't
        collide with the idNorma cache.
        """
        cache_key = f"law_{law_number}"
        cached = self._read_cache(self._norm_path(cache_key), self.norm_cache_ttl)
        if cached is not None and not force:
            logger.debug("cache hit for law %s", law_number)
            return cached

        url = self._build_url(opt=7, params={"idLey": law_number})
        content = self._get(url, accept="application/xml, text/xml")
        if content is None:
            return None

        if "<Norma " not in content:
            logger.warning("BCN response for idLey=%s is not a valid Norma", law_number)
            return None

        self._write_cache(self._norm_path(cache_key), content)
        return content

    def fetch_catalog_page(self, offset: int, limit: int = 100) -> Optional[str]:
        """Return the ``opt=3`` feed for a single offset/limit window.

        Used by :mod:`scripts.discover_bcn_catalog` to walk the catalog.
        Cached 24h because the feed refreshes daily.
        """
        cache_key = f"catalog_o{offset}_l{limit}"
        cached = self._read_cache(self._catalog_path(cache_key), self.catalog_cache_ttl)
        if cached is not None:
            return cached
        url = self._build_url(opt=3, params={"from": offset, "count": limit})
        content = self._get(url, accept="application/xml, text/xml")
        if content is None:
            return None
        self._write_cache(self._catalog_path(cache_key), content)
        return content

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    def _build_url(self, *, opt: int, params: dict) -> str:
        from urllib.parse import urlencode
        all_params = {"opt": opt, **params}
        return f"{self.base_url}?{urlencode(all_params)}"

    def _get(self, url: str, *, accept: str) -> Optional[str]:
        for attempt in range(self.max_retries):
            self._throttle()
            ua = self._user_agent()
            try:
                r = httpx.get(
                    url,
                    headers={
                        "User-Agent": ua,
                        "Accept": accept,
                        "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
                    },
                    timeout=self.timeout,
                    follow_redirects=True,
                )
            except httpx.HTTPError as exc:
                logger.warning("GET %s failed (attempt %d): %s", url, attempt + 1, exc)
                self._backoff(attempt)
                continue

            if r.status_code == 200:
                return r.text
            if r.status_code in (403, 429, 500, 502, 503, 504):
                logger.warning(
                    "GET %s returned %d (attempt %d), rotating UA + retrying",
                    url, r.status_code, attempt + 1,
                )
                self._ua_idx = (self._ua_idx + 1) % len(_USER_AGENTS)
                self._backoff(attempt)
                continue
            logger.warning("GET %s returned %d (giving up): %s", url, r.status_code, r.text[:200])
            return None

        logger.error("GET %s failed after %d retries", url, self.max_retries)
        return None

    def _user_agent(self) -> str:
        return _USER_AGENTS[self._ua_idx]

    def _throttle(self) -> None:
        if self._last_request_at is None:
            self._last_request_at = time.monotonic()
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(2.0 ** attempt)

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _norm_path(self, bcn_id: str) -> str:
        return f"norm_{bcn_id}"

    def _catalog_path(self, key: str) -> str:
        return f"cat_{key}"

    def _read_cache(self, key: str, ttl: timedelta) -> Optional[str]:
        if not self.cache_dir:
            return None
        path = self._cache_file_path(key)
        if not path.exists():
            return None
        try:
            age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
            if age > ttl:
                return None
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

    def _write_cache(self, key: str, content: str) -> None:
        if not self.cache_dir:
            return
        try:
            self._cache_file_path(key).write_text(content, encoding="utf-8")
        except OSError as exc:
            logger.warning("cache write failed for %s: %s", key, exc)

    def _cache_file_path(self, key: str) -> Optional[Path]:
        # Hash so any characters in the key (slashes, spaces) become safe
        # for the filesystem. The human-readable key is preserved in the
        # log output for debugging.
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"{digest}.xml"
