import logging as _logging
import uuid as _uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.deps.auth import get_current_user
from app.api.endpoints import (
    admin,
    agents,
    analysis,
    auth,
    chat,
    clients,
    deadline_alerts,
    document_analysis,
    document_generator,
    documents,
    feedback,
    lawyer,
    legal_areas,
    matters,
    metrics,
    organizations,
    precedents,
    saas,
    search,
    templates,
)
from app.core.config import settings
from app.models.user import User

_app_logger = _logging.getLogger("lilian.errors")


def _run_startup_migrations() -> None:
    """Run idempotent DB migrations on application startup.

    Why this lives here instead of in ``start.sh``:

      - The Railway service was reconfigured in the UI to use
        ``RAILPACK`` instead of the Dockerfile, so ``start.sh`` no
        longer runs. Railpack auto-detects Python and starts uvicorn
        directly.
      - Putting the heal here guarantees it runs on every container
        boot, regardless of builder (Dockerfile, Nixpacks, Railpack).
      - Each statement is idempotent (``ADD VALUE IF NOT EXISTS``,
        ``ADD COLUMN IF NOT EXISTS``, conditional ``UPDATE``), so
        repeated boots are cheap and safe.
    """
    try:
        from migrations.fix_matter_status_enum import main as _heal
        _heal()
    except Exception as exc:  # pragma: no cover - never block startup
        _app_logger.warning(
            "startup migration fix_matter_status_enum failed (continuing): %s",
            exc,
        )


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _app_logger.info(
        "lilian api starting — build marker commit=%s",
        "e62134f-fix-migration-lifespan",
    )
    _run_startup_migrations()
    yield


app = FastAPI(
    title="lilIAn - API",
    description="Plataforma legaltech chilena asistida por IA",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=_lifespan,
)


def _error_envelope(
    detail: str,
    request_id: str,
    *,
    error_type: str | None = None,
    extra: dict | None = None,
) -> dict:
    body = {
        "detail": detail,
        "request_id": request_id,
        "error_type": error_type,
    }
    if extra:
        body.update(extra)
    return body


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Attach a stable request_id to every request and response.

    The id flows into the JSON error envelope when exceptions bubble up
    so the frontend can quote it in bug reports.
    """
    request_id = request.headers.get("x-request-id") or str(_uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic / FastAPI request-body validation: return 422 with JSON."""
    request_id = getattr(request.state, "request_id", str(_uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_envelope(
            detail="Request validation failed",
            request_id=request_id,
            error_type="validation_error",
            extra={"errors": exc.errors()},
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last-resort handler.

    Before this existed, an unhandled exception inside a route returned
    a plain ``Internal Server Error`` text body with no JSON, no
    request_id, and (worst) occasionally poisoned the shared DB session
    so subsequent requests on unrelated paths also returned 500. The
    handler logs the full traceback server-side, returns a JSON envelope
    the frontend can parse, and crucially does NOT re-raise: the
    request lifecycle ends here so the next request starts clean.
    """
    request_id = getattr(request.state, "request_id", str(_uuid.uuid4()))
    _app_logger.exception(
        "unhandled exception on %s %s (request_id=%s)",
        request.method, request.url.path, request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_envelope(
            detail=f"{type(exc).__name__}: {exc}",
            request_id=request_id,
            error_type=type(exc).__name__,
        ),
    )

# S7-05: compress responses larger than 1KB to cut bandwidth for
# analytics / list endpoints. Mounted BEFORE CORS so the
# Vary: Accept-Encoding header is set correctly.
app.add_middleware(GZipMiddleware, minimum_size=1_000)

# CORS configuration (S1-17)
# - In production we require an explicit, comma-separated allow-list of
#   origins. Wildcard (`*`) is REJECTED at startup to avoid exposing the
#   API to any origin (even without credentials, this enables CSRF-style
#   abuse via top-level GETs).
# - In development we allow the explicit list (typically
#   ``http://localhost:3000``) or fall back to a sane default that still
#   excludes the wildcard.
# - Credentials are NEVER enabled when any wildcard-like origin slips
#   through, since the CORS spec forbids that combination.
raw_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
had_wildcard = any(o.lower() in {"*", "null"} for o in raw_origins)

allowed_origins = settings.get_allowed_origins()

if not allowed_origins:
    # Safe development defaults so the API still boots locally.
    allowed_origins = ["http://localhost:3000"]

allow_credentials = True
if had_wildcard:
    # CORS spec: wildcard + credentials is forbidden. Force credentials
    # off rather than crashing so the dev server can still start, but log
    # so the misconfiguration is visible.
    import logging

    logging.getLogger(__name__).warning(
        "ALLOWED_ORIGINS contained a wildcard; disabling CORS credentials "
        "to comply with the CORS spec."
    )
    allow_credentials = False

allow_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
allow_headers = ["Authorization", "Content-Type", "X-Requested-With"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=allow_methods,
    allow_headers=allow_headers,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(matters.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(document_analysis.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(lawyer.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(saas.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(clients.router, prefix="/api/v1")
app.include_router(legal_areas.router, prefix="/api/v1")
app.include_router(deadline_alerts.router, prefix="/api/v1")
app.include_router(document_generator.router, prefix="/api/v1")
app.include_router(precedents.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(metrics.router)


@app.get("/")
def root():
    return {"message": "lilIAn API", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/admin/run-migrations", tags=["admin"])
def run_migrations_endpoint(
    current_user: User = Depends(get_current_user),
) -> dict:
    """One-shot admin endpoint to run the startup migrations manually.

    Uses a raw ``psycopg2`` connection in autocommit mode because
    SQLAlchemy's ``execution_options(isolation_level="AUTOCOMMIT")``
    silently rolls back ``ALTER TYPE ... ADD VALUE`` on Postgres.

    Safe to call repeatedly: every statement is idempotent
    (``ADD VALUE IF NOT EXISTS``, ``ADD COLUMN IF NOT EXISTS``,
    conditional ``UPDATE``).
    """
    import logging
    import os

    import psycopg2

    raw_url = os.environ.get("DATABASE_URL", "")
    conn = psycopg2.connect(
        raw_url.replace("postgresql+psycopg2://", "postgresql://")
    )
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("ALTER TYPE matterstatus ADD VALUE IF NOT EXISTS 'failed'")
        cur.execute("ALTER TABLE matters ADD COLUMN IF NOT EXISTS last_error TEXT")
        cur.execute(
            """
            UPDATE matters
               SET status = 'failed', last_error = SUBSTR(status, 7)
             WHERE status LIKE 'error:%' AND last_error IS NULL
            """
        )
        healed = cur.rowcount
        cur.execute("SELECT enum_range(NULL::matterstatus)::text")
        enum_values = cur.fetchone()[0]
        cur.close()
        logging.getLogger("lilian.admin").info(
            "run-migrations completed; healed=%d enum=%s", healed, enum_values
        )
        return {
            "healed_rows": healed,
            "enum_values": enum_values,
            "status": "ok",
        }
    finally:
        conn.close()


@app.post("/admin/force-fix-enum", tags=["admin"])
def force_fix_enum_endpoint(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Last-resort endpoint that uses a raw psycopg2 connection in
    AUTOCOMMIT mode to force ``ALTER TYPE matterstatus ADD VALUE
    'failed'``.

    The lifespan / ``run-migrations`` endpoint uses SQLAlchemy's
    ``execution_options(isolation_level="AUTOCOMMIT")``, which on
    Postgres + SQLAlchemy 2.0 sometimes silently rolls back the
    DDL. This endpoint drops to the DBAPI directly so the ALTER TYPE
    is guaranteed to commit.
    """
    import logging
    import os

    import psycopg2

    raw_url = os.environ.get("DATABASE_URL", "")
    # SQLAlchemy sometimes prefixes the URL with ``postgresql+psycopg2://``.
    conn = psycopg2.connect(raw_url.replace("postgresql+psycopg2://", "postgresql://"))
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("ALTER TYPE matterstatus ADD VALUE IF NOT EXISTS 'failed'")
        cur.execute("ALTER TABLE matters ADD COLUMN IF NOT EXISTS last_error TEXT")
        cur.execute(
            """
            UPDATE matters
               SET status = 'failed', last_error = SUBSTR(status, 7)
             WHERE status LIKE 'error:%' AND last_error IS NULL
            """
        )
        healed = cur.rowcount
        cur.execute(
            "SELECT enum_range(NULL::matterstatus)::text"
        )
        enum_values = cur.fetchone()[0]
        cur.close()
    finally:
        conn.close()

    logging.getLogger("lilian.admin").info(
        "force-fix-enum completed; healed=%d enum=%s", healed, enum_values
    )
    return {"healed_rows": healed, "enum_values": enum_values, "status": "ok"}


@app.post("/admin/test-anthropic-raw", tags=["admin"])
def test_anthropic_raw_endpoint(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Bypasses the entire analysis pipeline and invokes
    ``AnthropicLLM.generate_structured`` directly with a tiny synthetic
    schema. The response is returned verbatim so we can see whether
    the LLM provider is reachable and what the raw text looks like.

    If the response carries ``{"error": "..."}`` then the provider
    path is broken; otherwise it shows what Claude actually emitted.
    """
    import logging

    from app.services.llm import get_llm_provider

    log = logging.getLogger("lilian.admin")
    provider = get_llm_provider()

    test_schema = {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "echo": {"type": "string"},
        },
        "required": ["ok", "echo"],
    }

    test_prompt = (
        "DOCUMENTO DE PRUEBA: La Ley 18916 establece el Código Aeronáutico.\n\n"
        "Responde con un objeto JSON válido que tenga ``ok=true`` y "
        "``echo`` igual a ``received``."
    )

    log.info("test-anthropic-raw: invoking provider=%s", type(provider).__name__)
    result = provider.generate_structured(
        prompt=test_prompt,
        system_prompt="Eres un asistente de prueba.",
        schema=test_schema,
    )
    log.info("test-anthropic-raw: result=%s", str(result)[:500])

    return {
        "provider": type(provider).__name__,
        "provider_model": getattr(provider, "model", "unknown"),
        "result": result,
    }
