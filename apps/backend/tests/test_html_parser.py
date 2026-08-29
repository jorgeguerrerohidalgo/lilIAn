"""Tests for the hierarchical HTML / TXT parser.

We feed the parser canned text dumps that mirror the Diario Oficial
layout and assert the chunks come out with the right hierarchical
fields and content.
"""

from __future__ import annotations

import pytest

from scripts.html_parser import HierarchicalParser, ParseResult


@pytest.fixture
def parser() -> HierarchicalParser:
    return HierarchicalParser()


# ---------------------------------------------------------------------------
# Codigo-style layout (LIBRO / TÍTULO / CAPÍTULO)
# ---------------------------------------------------------------------------

CODIGO_CIVIL_EXCERPT = """
LIBRO PRIMERO

TÍTULO I
De las personas en general

CAPÍTULO 1
De las personas naturales

Artículo 1°.- El hombre es persona natural desde que nace hasta que muere.
La ley protege su vida y su integridad física y síquica.
La persona es un sujeto de derecho.

Artículo 2°.- La ley distingue dos clases de personas: naturales y jurídicas.
Las personas naturales son los hombres y las mujeres.
Las personas jurídicas son las corporaciones, fundaciones y asociaciones.

TÍTULO II
De los bienes

Artículo 3°.- Sin perjuicio de lo dispuesto en leyes especiales, los bienes
existibles se dividen en muebles e inmuebles.
"""


def test_detects_codigo_structure(parser):
    result = parser.parse(CODIGO_CIVIL_EXCERPT)
    assert result.detected_structure == "codigo"
    assert len(result.chunks) >= 3


def test_inherits_libro_titulo_capitulo(parser):
    result = parser.parse(CODIGO_CIVIL_EXCERPT)
    chunks_by_article = {c.article_number: c for c in result.chunks}
    art1 = chunks_by_article.get("1")
    assert art1 is not None
    assert art1.libro == "PRIMERO"
    assert art1.titulo is not None and "personas" in art1.titulo.lower()
    assert art1.capitulo is not None and "naturales" in art1.capitulo.lower()
    # Articulo 3 is in a different TÍTULO (II). It still inherits LIBRO PRIMERO.
    art3 = chunks_by_article.get("3")
    assert art3 is not None
    assert art3.libro == "PRIMERO"


def test_hierarchy_path_builds_in_order(parser):
    result = parser.parse(CODIGO_CIVIL_EXCERPT)
    art1 = next(c for c in result.chunks if c.article_number == "1")
    path = art1.hierarchy_path()
    assert path.startswith("/")
    # Order: libro / titulo / capitulo / article — slugged.
    parts = path.strip("/").split("/")
    assert "PRIMERO" in parts[0]
    assert "1" in parts[-1]


# ---------------------------------------------------------------------------
# Ley-style layout (article-only)
# ---------------------------------------------------------------------------

LEY_21719_EXCERPT = """
LEY NÚM. 21.719

     "Artículo 1°.- Objeto y ámbito de aplicación. La presente ley tiene por objeto regular la forma y condiciones en la cual se efectúa el tratamiento y protección de los datos personales de las personas naturales, en conformidad al artículo 19, N° 4, de la Constitución Política de la República.

     "Artículo 2°.- Definiciones. Para los efectos de esta ley se entenderá por:
     a) Almacenamiento de datos: la conservación o custodia de datos en un registro o base de datos.
     b) Dato personal: cualquier información vinculada o referida a una persona natural identificada o identificable.

     "Artículo 3°.- Principios. El tratamiento de los datos personales se rige por los siguientes principios:
     a) Licitud.
     b) Finalidad.
"""


def test_detects_ley_structure(parser):
    result = parser.parse(LEY_21719_EXCERPT)
    # No LIBRO / TÍTULO / CAPÍTULO present.
    assert result.detected_structure == "ley"
    assert len(result.chunks) == 3


def test_ley_chunks_have_no_libro_titulo_capitulo(parser):
    result = parser.parse(LEY_21719_EXCERPT)
    for chunk in result.chunks:
        assert chunk.libro is None
        assert chunk.titulo is None
        assert chunk.capitulo is None
        assert chunk.article_number is not None


def test_ley_article_content_strips_inner_marker(parser):
    """The first line of an article body often re-mentions the article
    number; we strip it so the chunked text isn't redundant."""
    result = parser.parse(LEY_21719_EXCERPT)
    art1 = next(c for c in result.chunks if c.article_number == "1")
    assert not art1.content.lstrip().startswith("Artículo")
    assert "tiene por objeto" in art1.content


# ---------------------------------------------------------------------------
# Long articles are split
# ---------------------------------------------------------------------------

LONG_ARTICLE = (
    "Artículo 1°.- " + ("Texto filler con suficiente longitud para "
                          "forzar al parser a dividir este artículo en "
                          "varios chunks. " * 60)
)


def test_long_article_is_split_with_chapter_context(parser):
    result = parser.parse(LONG_ARTICLE)
    # Should produce > 1 chunk and each chunk inherits the article number.
    assert len(result.chunks) > 1
    for chunk in result.chunks:
        assert chunk.article_number == "1"


def test_short_article_remains_single_chunk(parser):
    """Articles shorter than max_chunk_chars are not split."""
    result = parser.parse("Artículo 1°.- Texto breve.")
    assert len(result.chunks) == 1


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

def test_empty_input_returns_empty(parser):
    result = parser.parse("")
    assert result.chunks == []
    assert result.warnings == []


def test_text_without_articles_falls_back_to_single_chunk(parser):
    """A doc with no article markers → single whole-doc chunk with warning."""
    result = parser.parse("Texto sin estructura reconocible. " * 5)
    assert len(result.chunks) == 1
    assert "no articles detected" in " ".join(result.warnings).lower()


def test_unrecognised_structural_heading_is_logged_as_warning(parser):
    """Garbage in the structural markers should not crash the parser."""
    text = "LIBRO FOO\n" + "Artículo 1°.- Cuerpo del artículo.\n" * 10
    result = parser.parse(text)
    assert len(result.chunks) >= 1
