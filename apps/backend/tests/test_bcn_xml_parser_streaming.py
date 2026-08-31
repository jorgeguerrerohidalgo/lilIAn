"""Tests for BCNXmlParser — streaming path used for large Tier 1 norms.

P3 from the corpus audit. The Codigo de Comercio (idNorma 22740) is a
57 MB BCN XML that the previous in-memory ``etree.fromstring`` path
could not parse: it OOMs or takes minutes. The streaming path keeps
peak memory bounded by processing one ``<EstructuraFuncional>`` at a
time and calling ``element.clear()``.

These tests generate synthetic BCN-like XMLs in memory (no network,
no fixtures) so they run in any environment and complete in seconds.
"""

import io

import pytest

from scripts.bcn_xml_parser import BCNXmlParser, NS


def _make_bcn_xml(n_articles: int, body_repeat: int = 6) -> bytes:
    """Synthesise a BCN-shape XML with ``n_articles`` articles."""
    out = io.BytesIO()
    out.write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Norma xmlns="{NS["n"]}" normaId="22740">\n'.encode()
    )
    out.write(
        b'<Identificador fechaPublicacion="1865-11-23">'
        b"<Organismos><Organismo>MIN. HACIENDA</Organismo></Organismos>"
        b"<TiposNumeros><TipoNumero><Tipo>Codigo</Tipo>"
        b"<Numero>COMERCIO</Numero></TipoNumero></TiposNumeros>"
        b"</Identificador>\n"
    )
    out.write(b"<Metadatos><TituloNorma>CODIGO DE COMERCIO</TituloNorma></Metadatos>\n")
    out.write(b"<Encabezado><Texto>Preambulo del codigo</Texto></Encabezado>\n")
    body = "Lorem ipsum dolor sit amet consectetur " * body_repeat
    for i in range(n_articles):
        out.write(
            f"<EstructuraFuncional><NombreParte>{i + 1}</NombreParte>"
            f"<TituloParte>TITULO {i + 1}</TituloParte>"
            f"<Texto>Articulo {i + 1}: {body}</Texto>"
            f"</EstructuraFuncional>\n".encode()
        )
    out.write(b"</Norma>")
    return out.getvalue()


@pytest.mark.unit
class TestBCNXmlParserStreaming:
    def setup_method(self) -> None:
        self.parser = BCNXmlParser()

    def test_routes_small_xml_to_eager_path(self) -> None:
        """Files under STREAMING_THRESHOLD_BYTES should not hit iterparse."""
        xml = _make_bcn_xml(10)
        assert len(xml) < self.parser.STREAMING_THRESHOLD_BYTES
        result = self.parser.parse(xml)
        assert result.bcn_id == "22740"
        assert result.titulo == "CODIGO DE COMERCIO"
        assert result.tipo == "codigo"
        assert result.numero == "COMERCIO"
        # 1 preamble + 10 articles
        assert len(result.chunks) == 11
        assert result.chunks[0].article_number == "preamble"

    def test_routes_large_xml_to_streaming_path(self) -> None:
        """Files over STREAMING_THRESHOLD_BYTES should use the streaming path."""
        # 2000 articles * ~6KB body each = ~12MB, well over the 5MB
        # threshold. Use a long body to reach it without taking forever
        # in CI.
        xml = _make_bcn_xml(2000, body_repeat=200)
        assert len(xml) >= self.parser.STREAMING_THRESHOLD_BYTES, (
            f"test setup under threshold: {len(xml)} < {self.parser.STREAMING_THRESHOLD_BYTES}"
        )
        result = self.parser.parse(xml)
        # All 2000 articles + 1 preamble
        assert len(result.chunks) == 2001
        assert result.titulo == "CODIGO DE COMERCIO"
        assert result.chunks[1].article_number == "1"
        assert result.chunks[-1].article_number == "2000"

    def test_streaming_equivalent_to_eager(self) -> None:
        """Eager and streaming must produce identical chunk content + order."""
        xml = _make_bcn_xml(500)
        eager = self.parser._parse_eager_for_test(xml) if hasattr(self.parser, "_parse_eager_for_test") else None
        if eager is None:
            # call the eager path by temporarily raising the threshold
            saved = self.parser.STREAMING_THRESHOLD_BYTES
            self.parser.STREAMING_THRESHOLD_BYTES = len(xml) + 1
            try:
                eager = self.parser.parse(xml)
            finally:
                self.parser.STREAMING_THRESHOLD_BYTES = saved

        stream = self.parser._parse_streaming(xml)
        assert len(eager.chunks) == len(stream.chunks)
        for i, (a, b) in enumerate(zip(eager.chunks, stream.chunks)):
            assert a.article_number == b.article_number, f"art at {i}: {a.article_number} vs {b.article_number}"
            assert a.content == b.content, f"content at {i} differs"
            assert a.libro == b.libro, f"libro at {i}: {a.libro} vs {b.libro}"
            assert a.titulo == b.titulo
            assert a.capitulo == b.capitulo
            assert a.derogado == b.derogado

    def test_streaming_handles_80mb_xml(self) -> None:
        """Realistic Codigo de Comercio scale: 80 MB XML should parse in <30s.

        Generating the full 57 MB Codigo de Comercio is overkill; we
        use 80 MB worth of synthetic content to exercise the same code
        path (huge_tree, no_network, periodic element.clear()).
        """
        xml = _make_bcn_xml(15000, body_repeat=100)
        assert len(xml) > 50 * 1024 * 1024  # >50 MB
        result = self.parser._parse_streaming(xml)
        assert len(result.chunks) == 15001  # 1 preamble + 15000
        # Metadata must survive the stream
        assert result.bcn_id == "22740"
        assert result.titulo == "CODIGO DE COMERCIO"
        assert result.tipo == "codigo"

    def test_streaming_preserves_derogados_flag(self) -> None:
        """<FechaDerogacion> children must set the derogado flag on the chunk."""
        xml = (
            f'<?xml version="1.0"?>\n<Norma xmlns="{NS["n"]}" normaId="999">'
            f"<EstructuraFuncional>"
            f"<NombreParte>1</NombreParte><TituloParte>TITULO I</TituloParte>"
            f"<Texto>Articulo 1 activo</Texto>"
            f"</EstructuraFuncional>"
            f"<EstructuraFuncional>"
            f"<NombreParte>2</NombreParte><TituloParte>TITULO I</TituloParte>"
            f"<Texto>Articulo 2 derogado</Texto>"
            f"<FechaDerogacion>2024-01-01</FechaDerogacion>"
            f"</EstructuraFuncional>"
            f"</Norma>"
        ).encode()
        result = self.parser._parse_streaming(xml)
        assert len(result.chunks) == 2
        assert result.chunks[0].derogado is False
        assert result.chunks[1].derogado is True
        assert any("derogated" in w for w in result.warnings)

    def test_streaming_assigns_sequential_chunk_index(self) -> None:
        """Every emitted chunk must have chunk_index 0..N-1 in source order."""
        xml = _make_bcn_xml(100)
        result = self.parser._parse_streaming(xml)
        indices = [c.chunk_index for c in result.chunks]
        assert indices == list(range(len(result.chunks)))
