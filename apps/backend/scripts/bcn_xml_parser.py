"""BCN XML parser for the corpus legal — replaces the regex-based
``html_parser.py`` for Tier 1+ norms.

BCN's legacy ``Consulta/obtxml`` endpoint returns XML structured per
``EsquemaIntercambioNorma-v1-0.xsd``. This parser walks that schema
and emits the same :class:`ParsedChunk` dataclass the rest of the
pipeline consumes, so the DBWriter + RAG + frontend are unchanged.

Sample response (Codigo Penal, abbreviated)::

    <?xml version="1.0" encoding="UTF-8"?>
    <Norma xmlns="http://www.leychile.cl/esquemas" normaId="1984">
      <Identificador fechaPromulgacion="1874-11-12" fechaPublicacion="1874-11-12">
        <TiposNumeros><TipoNumero><Tipo>Codigo</Tipo><Numero>PENAL</Numero></TipoNumero></TiposNumeros>
        <Organismos><Organismo>MINISTERIO DE JUSTICIA</Organismo></Organismos>
      </Identificador>
      <Metadatos>
        <TituloNorma>CODIGO PENAL</TituloNorma>
      </Metadatos>
      <Encabezado fechaVersion="..." derogado="...">
        <Texto>... preamble ...</Texto>
      </Encabezado>
      <EstructuraFuncional>
        <NombreParte>1</NombreParte>
        <TituloParte>DISPOSICIONES GENERALES</TituloParte>
        <Texto>El hombre es persona natural ...</Texto>
      </EstructuraFuncional>
      <EstructuraFuncional>
        <NombreParte>2</NombreParte>
        <Texto>La ley distingue ...</Texto>
        <FechaDerogacion>2026-12-01</FechaDerogacion>  <!-- if any -->
      </EstructuraFuncional>
    </Norma>

The parser is intentionally tolerant of optional fields. Anything it
cannot map cleanly gets logged as a warning and skipped, never
crashes the ingest.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from lxml import etree

# Re-export the canonical ParsedChunk from html_parser so the rest of
# the pipeline (db_writer, ingest_bcn_corpus) only ever sees one chunk
# class regardless of which parser produced it. Re-using the class
# avoids an isinstance() mismatch where the XML parser's chunks are
# rejected as "wrong type" by db_writer.upsert_chunks.
from scripts.html_parser import _INCISO_RE, ParsedChunk  # noqa: F401

logger = logging.getLogger("lilian.bcn_xml_parser")

# The single namespace BCN uses for the entire payload. Declared
# once so the rest of the parser doesn't repeat the long URI.
NS = {"n": "http://www.leychile.cl/esquemas"}

# ``<EstructuraFuncional>`` wrappers occasionally nest (Book →
# Title → Chapter). We track the active parent label so each chunk
# inherits the right LIBRO / TÍTULO / CAPÍTULO.
_BOOK_RE = re.compile(r"^LIBRO\b", re.IGNORECASE)
_TITLE_RE = re.compile(r"^T[ÍI]TULO\b", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"^CAP[ÍI]TULO\b|^P[ÁA]RRAFO\b", re.IGNORECASE)


@dataclass
class ParseResult:
    chunks: list[ParsedChunk] = field(default_factory=list)
    bcn_id: Optional[str] = None
    titulo: Optional[str] = None
    fecha_publicacion: Optional[str] = None
    organismo: Optional[str] = None
    tipo: Optional[str] = None
    numero: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


class BCNXmlParser:
    """Stateful walker over a single BCN norm XML.

    Usage::

        parser = BCNXmlParser(max_chunk_chars=2200)
        result = parser.parse(open("codigo_penal.xml").read())
        for chunk in result.chunks:
            print(chunk.hierarchy_path(), chunk.content[:80])
    """

    # Some norms have a long preamble (Encabezado) that isn't an
    # article. We prepend it to article 1 with a ``preamble`` tag so
    # the chunk sequence still makes sense.
    PREAMBLE_TAG = "preamble"

    # Codigo de Comercio is 57 MB and the previous in-memory
    # ``etree.fromstring`` would OOM or take minutes. Above this size
    # we always use the streaming ``iterparse`` path even for
    # small-file callers — the cost is one extra branch.
    STREAMING_THRESHOLD_BYTES = 5 * 1024 * 1024

    def __init__(self, *, max_chunk_chars: int = 2200) -> None:
        self.max_chunk_chars = max_chunk_chars

    def _split_oversized(
        self,
        *,
        article_number: str,
        libro: Optional[str],
        titulo: Optional[str],
        capitulo: Optional[str],
        parent_hint: str,
        body: str,
        derogado: bool,
        result: ParseResult,
    ) -> list[ParsedChunk]:
        """If ``body`` exceeds ``max_chunk_chars``, split at inciso
        boundaries when available, else naive window. Mirrors the
        logic in ``html_parser.HierarchicalParser._split_oversized``
        so behaviour is consistent across both parsers."""
        if len(body) <= self.max_chunk_chars:
            return [ParsedChunk(
                article_number=article_number,
                libro=libro,
                titulo=titulo,
                capitulo=capitulo,
                content=body.strip(),
                parent_hint=parent_hint,
                derogado=derogado,
            )]

        # First try to split at inciso boundaries (Latin American
        # legal style: Inciso primero, Inciso segundo, ...).
        inciso_matches = list(_INCISO_RE.finditer(body))
        if len(inciso_matches) >= 2:
            chunks = []
            for i, m in enumerate(inciso_matches):
                start = m.start()
                end = inciso_matches[i + 1].start() if i + 1 < len(inciso_matches) else len(body)
                sub = body[start:end].strip()
                if sub:
                    chunks.append(ParsedChunk(
                        article_number=article_number,
                        libro=libro,
                        titulo=titulo,
                        capitulo=capitulo,
                        content=sub,
                        parent_hint=parent_hint,
                        derogado=derogado,
                    ))
            return chunks

        # Naive window at max_chunk_chars, preserving word boundaries.
        chunks = []
        for k in range(0, len(body), self.max_chunk_chars):
            sub = body[k:k + self.max_chunk_chars].rsplit(" ", 1)[0]
            if sub:
                chunks.append(ParsedChunk(
                    article_number=article_number,
                    libro=libro,
                    titulo=titulo,
                    capitulo=capitulo,
                    content=sub,
                    parent_hint=parent_hint,
                    derogado=derogado,
                ))
        result.warnings.append(
            f"article {article_number} exceeded max_chunk_chars "
            f"({len(body)} chars); split naively"
        )
        return chunks

    def parse(self, xml_bytes: bytes | str) -> ParseResult:
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode("utf-8")

        if len(xml_bytes) >= self.STREAMING_THRESHOLD_BYTES:
            return self._parse_streaming(xml_bytes)

        result = ParseResult()
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            result.warnings.append(f"XML parse error: {exc}")
            return result

        result.bcn_id = root.get("normaId")
        result.titulo = _txt(root.find("./n:Metadatos/n:TituloNorma", NS))

        id_node = root.find("./n:Identificador", NS)
        if id_node is not None:
            result.fecha_publicacion = id_node.get("fechaPublicacion")
            organismo_node = id_node.find("./n:Organismos/n:Organismo", NS)
            if organismo_node is not None and organismo_node.text:
                result.organismo = organismo_node.text.strip()
            tipo_numero = id_node.find("./n:TiposNumeros/n:TipoNumero", NS)
            if tipo_numero is not None:
                tipo_t = tipo_numero.findtext("./n:Tipo", namespaces=NS)
                numero_t = tipo_numero.findtext("./n:Numero", namespaces=NS)
                if tipo_t:
                    result.tipo = tipo_t.strip().lower()
                if numero_t:
                    result.numero = numero_t.strip()

        # 1. Encabezado (preamble) — optional, attached to article 1.
        preamble_text = _txt(root.find("./n:Encabezado/n:Texto", NS))
        if preamble_text and len(preamble_text.strip()) >= 5:
            preamble_chunk = ParsedChunk(
                article_number=self.PREAMBLE_TAG,
                content=preamble_text.strip(),
                parent_hint="encabezado",
            )
            result.chunks.append(preamble_chunk)

        # 2. Walk every ``<EstructuraFuncional>`` and emit one chunk per
        #    article. Track parent labels across siblings so nested
        #    ``LIBRO`` / ``TÍTULO`` / ``CAPÍTULO`` headers propagate.
        current_libro: Optional[str] = None
        current_titulo: Optional[str] = None
        current_capitulo: Optional[str] = None

        for ef in root.iter(f"{{{NS['n']}}}EstructuraFuncional"):
            # Use ``.//n:X`` (anywhere in the subtree) instead of
            # ``./n:X`` (direct child) because BCN sometimes wraps the
            # article text in intermediate elements without changing
            # the visual structure. ``findtext`` with default returns
            # the first matching node's text; ``_txt`` normalises empty.
            article_num = _txt(ef.find(".//n:NombreParte", NS))
            titulo_parte = _txt(ef.find(".//n:TituloParte", NS))
            texto = _txt(ef.find(".//n:Texto", NS))
            fecha_derog = ef.find(".//n:FechaDerogacion", NS)

            # Process the heading FIRST so an article that carries
            # its own LIBRO/TÍTULO/CAPÍTULO marker inherits it
            # immediately (rather than only at the next sibling).
            if titulo_parte:
                titulo_norm = _normalize_label(titulo_parte)
                kind, ordinal = _split_heading(titulo_norm)
                if kind == "libro":
                    current_libro = ordinal
                elif kind == "titulo":
                    current_titulo = ordinal
                elif kind == "capitulo":
                    current_capitulo = ordinal

            if not article_num or not texto:
                # Headings without a Texto child are just context
                # updates — handled above.
                continue

            derogado = fecha_derog is not None
            if derogado:
                # Don't skip derogated chunks — keep them in the corpus
                # so the RAG has full historical context. The BCN marks
                # every Codigo Civil article as derogated because each
                # has been modified by a later ley, but the articles
                # themselves remain in force (partial derogation). The
                # flag in chunk_metadata.vigente lets the RAG filter
                # them out if the user wants only-current.
                result.warnings.append(
                    f"article {article_num} marked as derogated ({fecha_derog.text!r}) - kept in corpus"
                )

            if not texto.strip():
                continue

            parent_hint = " ".join(
                filter(None, [current_libro, current_titulo, current_capitulo, titulo_parte])
            )

            result.chunks.extend(self._split_oversized(
                article_number=article_num.strip(),
                libro=current_libro,
                titulo=current_titulo,
                capitulo=current_capitulo,
                parent_hint=parent_hint,
                body=texto.strip(),
                derogado=derogado,
                result=result,
            ))

        # Number chunks globally (1-based) so the DB row order matches.
        for i, chunk in enumerate(result.chunks):
            chunk.chunk_index = i

        return result

    def _parse_streaming(self, xml_bytes: bytes) -> ParseResult:
        """Streaming variant of :meth:`parse` for large BCN XMLs.

        Uses ``etree.iterparse`` with ``huge_tree=True`` so the entire
        document never lives in memory. ``element.clear()`` is called
        on every processed ``<EstructuraFuncional>`` and on the
        ``<Norma>`` root after each batch so lxml can release the
        memory it just consumed.

        Behaviour matches the eager :meth:`parse` exactly: same
        chunk ordering, same hierarchy tracking, same derogado flag.
        """
        result = ParseResult()
        ns_tag = f"{{{NS['n']}}}EstructuraFuncional"
        root_tag = f"{{{NS['n']}}}Norma"

        # ``huge_tree=True`` lifts libxml2's hardcoded 10 MB size
        # limit; BCN's 57 MB Codigo de Comercio trips the default
        # guard. ``resolve_entities=False`` keeps DTD processing off
        # the critical path. ``no_network=True`` blocks external
        # entity resolution (we never want to fetch from the BCN
        # network during a stream-parse).
        import io
        context = etree.iterparse(
            io.BytesIO(xml_bytes),
            events=("start", "end"),
            huge_tree=True,
            resolve_entities=False,
            no_network=True,
        )

        result.bcn_id = None
        result.titulo = None
        result.fecha_publicacion = None
        result.organismo = None
        result.tipo = None
        result.numero = None

        current_libro: Optional[str] = None
        current_titulo: Optional[str] = None
        current_capitulo: Optional[str] = None
        seen_estructura = 0
        norm_attrs_captured = False

        for event, elem in context:
            # Root metadata MUST be captured on the ``start`` event of
            # the <Norma> element. On its ``end`` event all children
            # have already been emitted and we lose the chance to read
            # the preamble.
            if not norm_attrs_captured and event == "start" and elem.tag == root_tag:
                result.bcn_id = elem.get("normaId")
                result.titulo = _txt(elem.find("./n:Metadatos/n:TituloNorma", NS))
                id_node = elem.find("./n:Identificador", NS)
                if id_node is not None:
                    result.fecha_publicacion = id_node.get("fechaPublicacion")
                    org = id_node.find("./n:Organismos/n:Organismo", NS)
                    if org is not None and org.text:
                        result.organismo = org.text.strip()
                    tn = id_node.find("./n:TiposNumeros/n:TipoNumero", NS)
                    if tn is not None:
                        t = tn.findtext("./n:Tipo", namespaces=NS)
                        n = tn.findtext("./n:Numero", namespaces=NS)
                        if t:
                            result.tipo = t.strip().lower()
                        if n:
                            result.numero = n.strip()
                preamble_text = _txt(elem.find("./n:Encabezado/n:Texto", NS))
                if preamble_text and len(preamble_text.strip()) >= 5:
                    result.chunks.append(
                        ParsedChunk(
                            article_number=self.PREAMBLE_TAG,
                            content=preamble_text.strip(),
                            parent_hint="encabezado",
                        )
                    )
                norm_attrs_captured = True
                continue

            if event != "end" or elem.tag != ns_tag:
                continue

            # Same fields as the eager path.
            article_num = _txt(elem.find(".//n:NombreParte", NS))
            titulo_parte = _txt(elem.find(".//n:TituloParte", NS))
            texto = _txt(elem.find(".//n:Texto", NS))
            fecha_derog = elem.find(".//n:FechaDerogacion", NS)

            if titulo_parte:
                titulo_norm = _normalize_label(titulo_parte)
                kind, ordinal = _split_heading(titulo_norm)
                if kind == "libro":
                    current_libro = ordinal
                elif kind == "titulo":
                    current_titulo = ordinal
                elif kind == "capitulo":
                    current_capitulo = ordinal

            if not article_num or not texto:
                elem.clear()
                seen_estructura += 1
                continue

            derogado = fecha_derog is not None
            if derogado:
                result.warnings.append(
                    f"article {article_num} marked as derogated ({fecha_derog.text!r}) - kept in corpus"
                )

            if not texto.strip():
                elem.clear()
                seen_estructura += 1
                continue

            parent_hint = " ".join(
                filter(None, [current_libro, current_titulo, current_capitulo, titulo_parte])
            )
            result.chunks.extend(self._split_oversized(
                article_number=article_num.strip(),
                libro=current_libro,
                titulo=current_titulo,
                capitulo=current_capitulo,
                parent_hint=parent_hint,
                body=texto.strip(),
                derogado=derogado,
                result=result,
            ))

            # Release the element + its siblings so lxml can reuse the
            # memory. ``elem.getparent().clear()`` is a stronger
            # variant that drops the previous siblings too; we use it
            # periodically to bound peak memory.
            elem.clear()
            seen_estructura += 1
            if seen_estructura % 200 == 0:
                parent = elem.getparent()
                if parent is not None:
                    # Clears the prior siblings' tail; keeps attributes
                    # we may still need (root only has normaId, which
                    # we've already captured).
                    for sibling in list(parent):
                        if sibling is elem:
                            break
                        parent.remove(sibling)

        # Final cleanup: drop the root.
        # (the iterparse generator goes out of scope here)

        for i, chunk in enumerate(result.chunks):
            chunk.chunk_index = i

        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _txt(node) -> Optional[str]:
    """Return stripped text from a single XML node, or None if missing/empty."""
    if node is None:
        return None
    if node.text is None:
        return None
    s = node.text.strip()
    return s or None


def _normalize_label(label: str) -> str:
    """Normalise whitespace in BCN labels.

    BCN often emits ``"LIBRO  PRIMERO"`` (double space) and mixed-case
    headings like ``"LIBRO primero"``. We squash whitespace and
    capitalise the leading word so chunks emit a stable hierarchy.
    """
    s = re.sub(r"\s+", " ", label).strip()
    if not s:
        return s
    parts = s.split(" ", 1)
    parts[0] = parts[0].upper()
    return " ".join(parts)


def _split_heading(label: str) -> tuple[str, str]:
    """Return ``(kind, ordinal)`` for a BCN heading label.

    ``"LIBRO PRIMERO"``                              → ``("libro", "PRIMERO")``.
    ``"TITULO I"``                                    → ``("titulo", "I")``.
    ``"TITULO PRIMERO DE LOS DELITOS..."``            → ``("titulo", "PRIMERO")``.
    ``"CAPITULO 1"``                                  → ``("capitulo", "1")``.
    ``"PARRAFO 3"``                                   → ``("capitulo", "3")``.

    The ordinal is the **first token after the heading word**. BCN
    headings often append a descriptive title (e.g. "TITULO PRIMERO
    DE LOS DELITOS..."); we only keep the ordinal because the full
    descriptive text is already preserved in ``parent_hint`` and the
    ``hierarchy_path()``.

    Returns ``("", label)`` when the label doesn't match any prefix —
    the caller should keep the full label in ``parent_hint`` so it
    doesn't get lost.
    """
    if _BOOK_RE.match(label):
        rest = label[len("LIBRO"):].strip()
        return ("libro", rest.split()[0] if rest else "")
    if _TITLE_RE.match(label):
        rest = label[len("TITULO"):].strip()
        return ("titulo", rest.split()[0] if rest else "")
    if _CHAPTER_RE.match(label):
        # "CAPITULO 1" → drop "CAPITULO". "PARRAFO 3" → drop "PARRAFO".
        ordinal = re.sub(r"^(CAPITULO|PARRAFO)\s*", "", label, flags=re.IGNORECASE).strip()
        return ("capitulo", ordinal.split()[0] if ordinal else "")
    return ("", label)
