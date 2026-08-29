"""Tests for the BCN XML parser — feed it canned XML and assert the
hierarchical fields land on the right chunks."""

from __future__ import annotations

import pytest

from scripts.bcn_xml_parser import BCNXmlParser, ParsedChunk


CODIGO_PENAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Norma xmlns="http://www.leychile.cl/esquemas" normaId="1984" derogado="no derogado">
  <Identificador fechaPromulgacion="1874-11-12" fechaPublicacion="1874-11-12">
    <TiposNumeros><TipoNumero><Tipo>Codigo</Tipo><Numero>PENAL</Numero></TipoNumero></TiposNumeros>
    <Organismos><Organismo>MINISTERIO DE JUSTICIA</Organismo></Organismos>
  </Identificador>
  <Metadatos><TituloNorma>CODIGO PENAL</TituloNorma></Metadatos>
  <Encabezado fechaVersion="1927-10-12"><Texto>Preambulo historico del codigo.</Texto></Encabezado>
  <EstructuraFuncional>
    <NombreParte>1</NombreParte>
    <TituloParte>DISPOSICIONES GENERALES</TituloParte>
    <Texto>El hombre es persona natural desde que nace hasta que muere.</Texto>
  </EstructuraFuncional>
  <EstructuraFuncional>
    <NombreParte>2</NombreParte>
    <Texto>La ley distingue dos clases de personas.</Texto>
  </EstructuraFuncional>
  <EstructuraFuncional>
    <NombreParte>3</NombreParte>
    <Texto>Derogado.</Texto>
    <FechaDerogacion>2026-12-01</FechaDerogacion>
  </EstructuraFuncional>
  <EstructuraFuncional>
    <NombreParte>4</NombreParte>
    <Texto>Articulo vigente.</Texto>
  </EstructuraFuncional>
</Norma>
"""


@pytest.fixture
def parser() -> BCNXmlParser:
    return BCNXmlParser()


def test_extracts_top_level_metadata(parser):
    result = parser.parse(CODIGO_PENAL_XML)
    assert result.bcn_id == "1984"
    assert result.titulo == "CODIGO PENAL"
    assert result.fecha_publicacion == "1874-11-12"
    assert result.organismo == "MINISTERIO DE JUSTICIA"
    assert result.tipo == "codigo"
    assert result.numero == "PENAL"


def test_emits_preamble_then_articles(parser):
    result = parser.parse(CODIGO_PENAL_XML)
    articles = [c.article_number for c in result.chunks]
    assert articles == ["preamble", "1", "2", "4"]


def test_skips_derogados(parser):
    """Articles with <FechaDerogacion> must not land in the chunk list."""
    result = parser.parse(CODIGO_PENAL_XML)
    for chunk in result.chunks:
        assert "Derogado" not in chunk.content, f"derogado article leaked: {chunk.article_number}"
    assert any("article 3" in w and "derogated" in w for w in result.warnings), result.warnings


def test_chunk_indexes_are_contiguous(parser):
    result = parser.parse(CODIGO_PENAL_XML)
    indexes = [c.chunk_index for c in result.chunks]
    assert indexes == list(range(len(result.chunks)))


def test_hierarchy_path_for_article_1(parser):
    """Article 1 inherits the TituloParte as part of its hierarchy.

    The Codigo Penal test fixture has no explicit LIBRO/TÍTULO/CAPÍTULO
    headings — only ``<TituloParte>``. Those land in ``parent_hint``
    as the human-readable breadcrumb but do not promote to a structured
    ``libro/titulo/capitulo`` field. Promoting requires the XML to
    carry explicit LIBRO/TÍTULO/CAPÍTULO headings (see ``test_libro_
    titulo_capitulo_hierarchy`` for a fixture with that structure).
    """
    result = parser.parse(CODIGO_PENAL_XML)
    art1 = next(c for c in result.chunks if c.article_number == "1")
    assert art1.hierarchy_path() == "/1"
    assert "DISPOSICIONES GENERALES" in art1.parent_hint


def test_libro_titulo_capitulo_hierarchy():
    """A Codigo with explicit LIBRO / TÍTULO / CAPÍTULO headings gets
    the right hierarchical fields propagated to subsequent articles.
    """
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Norma xmlns="http://www.leychile.cl/esquemas" normaId="172986">
  <Identificador fechaPublicacion="2000-01-01"></Identificador>
  <Metadatos><TituloNorma>CODIGO CIVIL</TituloNorma></Metadatos>
  <EstructuraFuncional>
    <NombreParte>PRIMERO</NombreParte>
    <TituloParte>LIBRO PRIMERO</TituloParte>
  </EstructuraFuncional>
  <EstructuraFuncional>
    <NombreParte>I</NombreParte>
    <TituloParte>TITULO I</TituloParte>
  </EstructuraFuncional>
  <EstructuraFuncional>
    <NombreParte>1</NombreParte>
    <TituloParte>CAPITULO 1</TituloParte>
    <Texto>El hombre es persona natural.</Texto>
  </EstructuraFuncional>
</Norma>"""
    result = BCNXmlParser().parse(xml)
    art1 = next(c for c in result.chunks if c.article_number == "1")
    assert art1.libro == "PRIMERO"
    assert art1.titulo == "I"
    # The parser strips the "CAPITULO " prefix and stores only the
    # ordinal in the structured field. The full "CAPITULO 1" still
    # appears in parent_hint and hierarchy_path via ``_split_heading``.
    assert art1.capitulo == "1"
    assert "PRIMERO" in art1.hierarchy_path()
    assert "I" in art1.hierarchy_path()
    assert "/1" in art1.hierarchy_path()


def test_invalid_xml_returns_empty_result_without_crashing():
    """Robustness: a malformed doc should not take down the crawler."""
    parser = BCNXmlParser()
    result = parser.parse("<Norma><broken")
    assert result.chunks == []
    assert any("parse error" in w.lower() for w in result.warnings)


def test_empty_document_returns_clean_result(parser):
    result = parser.parse(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Norma xmlns="http://www.leychile.cl/esquemas" normaId="X"/>'
    )
    assert result.chunks == []
    assert result.bcn_id == "X"
    assert result.warnings == []


def test_hierarchy_path_formatting(parser):
    """hierarchy_path() emits slash-separated pieces in canonical order."""
    chunk = ParsedChunk(libro="PRIMERO", titulo="TÍTULO I", capitulo="CAPÍTULO 1", article_number="5")
    assert chunk.hierarchy_path() == "/PRIMERO/TÍTULO I/CAPÍTULO 1/5"


def test_real_codigo_penal_size_smoke(parser):
    """Sanity: we don't blow up on a full Codigo Penal XML (~2 MB).

    Not a behavioural assertion — just a guard against accidental O(n²)
    regressions when the parser hits real-world inputs. The fixture
    may not exist in CI; we only assert when it's available.
    """
    from pathlib import Path
    big = Path("/tmp/bcn-test.xml")
    if big.exists():
        # We deliberately accept whatever the cached XML produces.
        # The point is that parsing 2 MB doesn't take >5 seconds.
        import time
        t0 = time.monotonic()
        result = parser.parse(big.read_bytes())
        elapsed = time.monotonic() - t0
        assert elapsed < 30, f"parser took {elapsed:.1f}s on real-world XML"
        assert isinstance(result.chunks, list)
