#!/bin/sh
set -e
cd /app

# LLM calls can take 30-60s; BackgroundTasks (analysis, deadline generation,
# document classification) all queue on FastAPI's anyio threadpool. Default
# capacity (min(32, cpu+4)) saturates quickly when several analyses run in
# parallel and starves incoming HTTP requests, which is what produced the
# "trigger analysis → entire backend 500s" regression. Raising the limit to
# 128 keeps the pool comfortable for ~4 concurrent heavy tasks plus all
# the lightweight endpoints.
#
# ANYIO_MAX_THREADS must be set BEFORE Python starts so anyio picks it up
# at import time.
export ANYIO_MAX_THREADS=${ANYIO_MAX_THREADS:-128}

# Idempotent DB migration: heal any rows whose ``status`` carries the
# historical ``"error:..."`` prefix (no longer in the MatterStatus enum)
# and add the ``last_error`` column if it hasn't been added yet. Without
# this, every read of a matter row from a previous failed analysis
# raises a LookupError and crashes the request. See
# apps/backend/migrations/fix_matter_status_enum.py.
python -m migrations.fix_matter_status_enum || \
  echo "[start.sh] fix_matter_status_enum migration failed; continuing startup" >&2

exec python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port ${PORT:-8000} \
  --timeout-keep-alive 75 \
  --backlog 2048