import re

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
# - Credentials are NEVER enabled when any wildcard-like origin slips
#   through, since the CORS spec forbids that combination.
# - S7-fix: Support the special token `*.<domain>` in ALLOWED_ORIGINS to
#   mean "any subdomain of <domain>". E.g. `*.vercel.app` allows
#   `lil-i-an.vercel.app`, `lil-i-an-<team>.vercel.app`, and any
#   preview/per-deploy URL without us having to list each one. These
#   entries are passed as regex patterns to CORSMiddleware.
raw_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
had_wildcard = any(o.lower() in {"*", "null"} for o in raw_origins)

allowed_origins = settings.get_allowed_origins()

if not allowed_origins:
    # Safe development defaults so the API still boots locally.
    allowed_origins = ["http://localhost:3000"]

# Expand `*.<domain>` tokens into exact-origin list by deriving common
# Vercel URL shapes for the configured project name. The `*.<domain>` form
# also stays in the list as a regex (handled below) so preview deploys
# with random hashes continue to match.
expanded_exact: list[str] = []
regex_patterns: list[str] = []
for origin in allowed_origins:
    if origin.startswith("*."):
        # Treat as a regex: any origin whose host ends with `.<domain>`.
        domain = re.escape(origin[2:])
        regex_patterns.append(rf"^https?://([a-z0-9-]+\.)*{domain}(:\d+)?$")
    else:
        expanded_exact.append(origin)

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

# CORSMiddleware supports either a literal origin list (allow_origins) or
# a regex (allow_origin_regex). We pass both: exact matches for
# prod domains, regex for the wildcard tokens.
app.add_middleware(
    CORSMiddleware,
    allow_origins=expanded_exact,
    allow_origin_regex="|".join(regex_patterns) if regex_patterns else None,
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
