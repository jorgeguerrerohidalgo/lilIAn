from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.endpoints import (
    admin,
    analysis,
    auth,
    chat,
    clients,
    deadline_alerts,
    document_analysis,
    document_generator,
    documents,
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

app = FastAPI(
    title="lilIAn - API",
    description="Plataforma legaltech chilena asistida por IA",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
allowed_origins = [o for o in settings.get_allowed_origins() if o and o != "*"]

is_production = settings.APP_ENV.lower() == "production"
if is_production and not allowed_origins:
    raise RuntimeError(
        "ALLOWED_ORIGINS must be configured in production. "
        "Wildcard (`*`) origins are not permitted."
    )

if not allowed_origins:
    # Safe development defaults so the API still boots locally.
    allowed_origins = ["http://localhost:3000"]

allow_credentials = True
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
app.include_router(metrics.router)


@app.get("/")
def root():
    return {"message": "lilIAn API", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
