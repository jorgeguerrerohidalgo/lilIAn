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
from scripts.html_parser import ParsedChunk  # noqa: F401

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

        parser = BCNXmlParser()
        result = parser.parse(open("codigo_penal.xml").read())
        for chunk in result.chunks:
            print(chunk.hierarchy_path(), chunk.content[:80])
    """

    # Some norms have a long preamble (Encabezado) that isn't an
    # article. We prepend it to article 1 with a ``preamble`` tag so
    # the chunk sequence still makes sense.
    PREAMBLE_TAG = "preamble"

    def parse(self, xml_bytes: bytes | str) -> ParseResult:
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode("utf-8")
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

            chunk = ParsedChunk(
                article_number=article_num.strip(),
                libro=current_libro,
                titulo=current_titulo,
                capitulo=current_capitulo,
                content=texto.strip(),
                parent_hint=parent_hint,
                derogado=derogado,
            )
            result.chunks.append(chunk)

        # Number chunks globally (1-based) so the DB row order matches.
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
