"""Tests for the BCN HTTP XML client — no real network calls."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from scripts.bcn_http_client import BCNHttpClient


def _mock_xml_norm(bcn_id: str = "1984") -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Norma xmlns="http://www.leychile.cl/esquemas" normaId="{bcn_id}">'
        '<Metadatos><TituloNorma>CODIGO PENAL</TituloNorma></Metadatos>'
        '<Identificador fechaPublicacion="1874-11-12"></Identificador>'
        '<EstructuraFuncional><NombreParte>1</NombreParte>'
        '<TituloParte>DISPOSICIONES GENERALES</TituloParte>'
        '<Texto>El hombre es persona natural desde que nace hasta que muere.</Texto>'
        '</EstructuraFuncional>'
        '<EstructuraFuncional><NombreParte>2</NombreParte>'
        '<Texto>La ley distingue dos clases de personas.</Texto>'
        '</EstructuraFuncional>'
        '</Norma>'
    )


def _mock_catalog_page() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ResultadoConsulta>'
        '<NORMA idNorma="1984" tipoNorma="codigo" numero="2561" fechaPublicacion="1874-11-12">'
        '<Titulo>CODIGO PENAL</Titulo>'
        '</NORMA>'
        '<NORMA idNorma="207436" tipoNorma="codigo" numero="1" fechaPublicacion="2002-07-16">'
        '<Titulo>CODIGO DEL TRABAJO</Titulo>'
        '</NORMA>'
        '</ResultadoConsulta>'
    )


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Path:
    return tmp_path


def test_fetch_norm_xml_returns_content(tmp_cache, monkeypatch):
    captured = []

    def fake_send(self, *args, **kwargs):  # mirrors httpx.Response shape
        captured.append(kwargs.get("headers", {}).get("User-Agent"))
        r = httpx.Response(200, content=_mock_xml_norm().encode("utf-8"))
        return r

    monkeypatch.setattr(httpx.Client, "send", fake_send)

    # Build a minimal client that uses our patched transport.
    client = BCNHttpClient(cache_dir=tmp_cache)
    client._ua_idx = 0

    # Monkeypatch the actual transport method used by the client.
    captured_url = []
    orig_get = client._get

    def fake_get(url, *, accept):
        captured_url.append(url)
        return _mock_xml_norm()

    client._get = fake_get  # type: ignore[assignment]
    content = client.fetch_norm_xml("1984")
    assert content is not None
    assert "<Norma " in content
    assert 'normaId="1984"' in content
    assert "codigo_penal" in content.lower() or "CODIGO PENAL" in content
    assert "Consulta/obtxml" in captured_url[0]
    assert "idNorma=1984" in captured_url[0]
    assert "opt=7" in captured_url[0]


def test_fetch_norm_xml_uses_cache(tmp_cache):
    client = BCNHttpClient(cache_dir=tmp_cache)

    # Pre-populate cache.
    client._write_cache(client._norm_path("1984"), _mock_xml_norm())

    # Should read from disk, not make any HTTP call.
    client._get = lambda *a, **kw: pytest.fail("HTTP should not be called")  # type: ignore[assignment]
    content = client.fetch_norm_xml("1984")
    assert content is not None
    assert "<Norma " in content


def test_fetch_norm_xml_force_bypasses_cache(tmp_cache):
    client = BCNHttpClient(cache_dir=tmp_cache)
    client._write_cache(client._norm_path("1984"), "<Norma>cached</Norma>")

    called = {"n": 0}

    def fake_get(url, *, accept):
        called["n"] += 1
        return _mock_xml_norm()

    client._get = fake_get  # type: ignore[assignment]
    content = client.fetch_norm_xml("1984", force=True)
    assert called["n"] == 1
    assert "<Norma " in content


def test_fetch_catalog_page(tmp_cache):
    client = BCNHttpClient(cache_dir=tmp_cache)

    called = {"n": 0, "url": None}

    def fake_get(url, *, accept):
        called["n"] += 1
        called["url"] = url
        return _mock_catalog_page()

    client._get = fake_get  # type: ignore[assignment]
    content = client.fetch_catalog_page(offset=200, limit=50)
    assert called["n"] == 1
    assert "opt=3" in called["url"]
    assert "from=200" in called["url"]
    assert "count=50" in called["url"]
    assert content is not None
    assert "NORMA" in content


def test_cache_expiry(tmp_cache):
    client = BCNHttpClient(cache_dir=tmp_cache, norm_cache_ttl=timedelta(seconds=0))
    client._write_cache(client._norm_path("X"), "<Norma/>")

    # Force mtime into the past so the TTL check fails.
    path = client._cache_file_path(client._norm_path("X"))
    import os
    past = (datetime.now() - timedelta(hours=1)).timestamp()
    os.utime(path, (past, past))

    # With TTL = 0 seconds, every read should miss.
    assert client._read_cache(client._norm_path("X"), timedelta(seconds=0)) is None


def test_no_cache_dir_disables_cache_gracefully(tmp_path):
    client = BCNHttpClient(cache_dir=None)
    # All cache calls must be no-ops, not raise.
    client._write_cache("k", "v")
    assert client._read_cache("k", timedelta(hours=1)) is None
    assert client._cache_file_path("k") is None
