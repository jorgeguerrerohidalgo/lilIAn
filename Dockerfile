# S6-01: multi-stage Dockerfile for the lilIAn backend.
# - builder: installs deps with the full toolchain
# - runtime: slim image, non-root user, healthcheck
#
# Build:  docker build -t lilian-api .
# Run:    docker run -p 8000:8000 --env-file apps/backend/.env lilian-api

# ---- Builder ----
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY apps/backend/requirements.txt ./requirements.txt
RUN pip install --prefix=/install -r requirements.txt

# ---- Runtime ----
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/install/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONPATH=/app

WORKDIR /app

# Install tesseract for OCR (workers) — keep small footprint.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user and copy the app
RUN groupadd --system appuser && useradd --system --gid appuser appuser \
    && mkdir -p /app/storage/documents \
    && chown -R appuser:appuser /app

COPY --chown=appuser:appuser apps/backend/ /app/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request, sys; \
    sys.exit(0) if urllib.request.urlopen('http://localhost:${PORT:-8000}/health', timeout=3).status == 200 else sys.exit(1)" \
  || exit 1

CMD ["sh", "start.sh"]