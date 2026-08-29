"""Tests for the BCN SPARQL client.

We exercise the parsing/serialisation helpers against canned SPARQL
JSON responses so we don't need a live endpoint. The HTTP layer is
monkey-patched via httpx_mock when needed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from scripts.bcn_client import BCNClient, _jsonable, BCN_NORMS_PREFIX


# ---------------------------------------------------------------------------
# _row_to_norm / parsing helpers
# ---------------------------------------------------------------------------

def test_row_to_norm_extracts_bcn_id():
    """The BCN URI ends with the bcn_id; we strip the prefix."""
    client = BCNClient(cache_dir=None)
    row = {
        "norma": {"value": f"{BCN_NORMS_PREFIX}resource/1984"},
        "titulo": {"value": "Código Penal"},
        "tipo": {"value": "codigo"},
        "numero": {"value": "2561"},
        "fecha": {"value": "1874-11-12"},
        "organismo": {"value": "Ministerio de Justicia"},
    }
    norm = client._row_to_norm(row)
    assert norm["bcn_id"] == "1984"
    assert norm["titulo"] == "Código Penal"
    assert norm["tipo"] == "codigo"
    assert norm["numero"] == "2561"
    assert norm["fecha_publicacion"] == "1874-11-12"
    assert norm["organismo_emisor"] == "Ministerio de Justicia"
    assert "1984" in norm["url_bcn"]


def test_row_to_norm_handles_missing_optionals():
    """fecha_publicacion, organismo and numero may be absent."""
    client = BCNClient(cache_dir=None)
    row = {
        "norma": {"value": f"{BCN_NORMS_PREFIX}resource/99"},
        "titulo": {"value": "Norma sin metadata"},
    }
    norm = client._row_to_norm(row)
    assert norm["bcn_id"] == "99"
    assert norm["fecha_publicacion"] is None
    assert norm["organismo_emisor"] is None
    assert norm["numero"] is None
    assert norm["tipo"] == "otro"  # default when missing


@pytest.mark.parametrize("raw,expected", [
    ("2024-12-13", "2024-12-13"),
    ("2024-12-13T00:00:00", "2024-12-13"),
    ("2024-12-13T00:00:00Z", "2024-12-13"),
    ("2024/12/13", "2024-12-13"),
    ("", None),
    (None, None),
    ("not-a-date", None),
    ("2024-12-13T15:30:45.123Z", "2024-12-13"),  # truncate to date
])
def test_parse_date_handles_common_formats(raw, expected):
    client = BCNClient(cache_dir=None)
    assert client._parse_date(raw) == expected


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_throttle_respects_min_interval(monkeypatch):
    """Back-to-back calls should sleep the difference to the interval."""
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.bcn_client.time.sleep", lambda s: sleeps.append(s))
    # Pretend 0.5s passed between the two _throttle calls so the
    # second one has to sleep 1.5s to satisfy the 2.0s interval.
    monotonic_values = iter([100.0, 100.5, 100.5])
    monkeypatch.setattr("scripts.bcn_client.time.monotonic", lambda: next(monotonic_values))

    client = BCNClient(min_interval_seconds=2.0, cache_dir=None)
    client._throttle()  # primes _last_request_at = 100.0
    client._throttle()  # elapsed = 0.5s, should sleep 1.5s
    assert sleeps, "expected at least one sleep"
    assert sleeps[0] >= 1.0


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def test_cache_round_trip(tmp_path: Path):
    client = BCNClient(cache_dir=tmp_path, cache_ttl=timedelta(hours=1))
    key = "test-key"
    payload = [{"bcn_id": "1984", "titulo": "Codigo Penal"}]
    client._write_cache(key, payload)

    # Second instance reads from the same dir.
    client2 = BCNClient(cache_dir=tmp_path, cache_ttl=timedelta(hours=1))
    cached = client2._read_cache(key)
    assert cached == payload


def test_cache_expires(tmp_path: Path):
    """Entries older than cache_ttl are dropped on read."""
    client = BCNClient(cache_dir=tmp_path, cache_ttl=timedelta(milliseconds=1))
    client._write_cache("k", [{"x": 1}])

    # Force both the file mtime AND the in-payload _fetched_at
    # timestamp into the past so the TTL check fails.
    path = client._cache_path("k")
    assert path is not None
    import json
    import os
    past_iso = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["_fetched_at"] = past_iso
    path.write_text(json.dumps(payload), encoding="utf-8")
    past = (datetime.utcnow() - timedelta(hours=1)).timestamp()
    os.utime(path, (past, past))

    fresh = BCNClient(cache_dir=tmp_path, cache_ttl=timedelta(milliseconds=10))
    assert fresh._read_cache("k") is None


# ---------------------------------------------------------------------------
# _jsonable
# ---------------------------------------------------------------------------

def test_jsonable_unwraps_sparql_bindings():
    assert _jsonable({"value": "foo"}) == "foo"
    assert _jsonable([{"value": 1}, {"value": 2}]) == [1, 2]
    assert _jsonable({"x": {"value": 1}, "y": "z"}) == {"x": 1, "y": "z"}
    assert _jsonable("plain") == "plain"
    assert _jsonable(42) == 42
