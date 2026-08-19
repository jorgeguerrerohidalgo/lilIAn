import logging as _logging
import uuid as _uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

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

_app_logger = _logging.getLogger("lilian.errors")


app = FastAPI(
    title="lilIAn - API",
    description="Plataforma legaltech chilena asistida por IA",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
