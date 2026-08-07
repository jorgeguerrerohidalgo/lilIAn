"""Regression tests for security fixes in Sprint 0."""
import pytest


def test_classify_document_async_defined_once():
    """S0-08: _classify_document_async must be defined only once.

    Regression: the function was previously defined twice in
    apps/backend/app/services/document_processor.py — the second
    silently overwrote the first, masking bugs and confusing future
    maintainers.
    """
    import inspect
    from app.services import document_processor

    source = inspect.getsource(document_processor)
    assert source.count("def _classify_document_async") == 1, (
        "_classify_document_async is defined more than once in "
        "document_processor.py — duplicate definition was reintroduced"
    )


def test_classify_document_async_uses_logger_not_print():
    """S0-08 + S0-02: the surviving definition must use logger, not print()."""
    import inspect
    from app.services import document_processor

    source = inspect.getsource(document_processor._classify_document_async)
    assert "logger" in source, "Expected logging usage"
    assert "print(" not in source, "print() must not be used in classify_document_async"