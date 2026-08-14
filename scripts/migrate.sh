#!/usr/bin/env bash
# ============================================
# lilIAn migrations automation (S6-B5 / S6-31)
# ============================================
#
# Applies SQL migrations in deterministic order. Designed for Supabase
# (and any other Postgres-compatible DB), but also falls back to the
# in-tree ``apps/backend/migrations`` directory if Supabase migrations
# aren't present.
#
# Features
#   * Detects ``$DATABASE_URL`` from the environment or accepts a
#     ``--database-url`` flag.
#   * Defaults to ``postgresql://postgres:postgres@localhost:5432/postgres``
#     when no connection string is configured.
#   * Lists ``infra/supabase/migrations/*.sql`` (preferred) or
#     ``apps/backend/migrations/*.sql`` (fallback), in lexical order.
#   * ``--dry-run`` prints the planned order without executing anything.
#   * Idempotent: tracks applied migrations in a ``_lilian_migrations``
#     table — already-applied files are skipped, not failed.
#   * Exits non-zero if psql is missing or any non-idempotent error
#     surfaces.
#
# Usage:
#   ./scripts/migrate.sh                 # apply pending migrations
#   ./scripts/migrate.sh --dry-run       # preview what would run
#   ./scripts/migrate.sh --database-url postgres://...
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SUPABASE_DIR="$REPO_ROOT/infra/supabase/migrations"
BACKEND_DIR="$REPO_ROOT/apps/backend/migrations"

DEFAULT_DB_URL="postgresql://postgres:postgres@localhost:5432/postgres"

DRY_RUN="false"
DB_URL=""

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    --database-url)
      DB_URL="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '2,28p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Run with --help for usage." >&2
      exit 2
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Resolve database URL
# ---------------------------------------------------------------------------
if [[ -z "$DB_URL" ]]; then
  if [[ -n "${DATABASE_URL:-}" ]]; then
    DB_URL="$DATABASE_URL"
  else
    DB_URL="$DEFAULT_DB_URL"
    echo "[migrate] DATABASE_URL not set; falling back to $DB_URL"
  fi
fi

# ---------------------------------------------------------------------------
# Discover migration files
# ---------------------------------------------------------------------------
MIGRATIONS=()
if compgen -G "$SUPABASE_DIR/*.sql" >/dev/null; then
  while IFS= read -r f; do
    MIGRATIONS+=("$f")
  done < <(ls -1 "$SUPABASE_DIR"/*.sql | sort)
  echo "[migrate] Found ${#MIGRATIONS[@]} migration(s) in infra/supabase/migrations/"
elif compgen -G "$BACKEND_DIR/*.sql" >/dev/null; then
  while IFS= read -r f; do
    MIGRATIONS+=("$f")
  done < <(ls -1 "$BACKEND_DIR"/*.sql | sort)
  echo "[migrate] Found ${#MIGRATIONS[@]} migration(s) in apps/backend/migrations/"
else
  echo "[migrate] No .sql migrations found in $SUPABASE_DIR or $BACKEND_DIR" >&2
  exit 1
fi

if [[ ${#MIGRATIONS[@]} -eq 0 ]]; then
  echo "[migrate] No migrations to apply."
  exit 0
fi

# ---------------------------------------------------------------------------
# Dry-run output
# ---------------------------------------------------------------------------
if [[ "$DRY_RUN" == "true" ]]; then
  echo "[migrate] DRY RUN — no changes will be made."
  echo "[migrate] Database URL: $DB_URL"
  echo "[migrate] Planned migration order:"
  for f in "${MIGRATIONS[@]}"; do
    echo "  - $(basename "$f")"
  done
  exit 0
fi

# ---------------------------------------------------------------------------
# Real run
# ---------------------------------------------------------------------------
if ! command -v psql >/dev/null 2>&1; then
  echo "[migrate] psql not found in PATH. Install Postgres client tools." >&2
  exit 1
fi

echo "[migrate] Connecting to: $DB_URL"

# Bootstrap the migrations tracking table if missing.
psql "$DB_URL" -v ON_ERROR_STOP=1 -q <<'SQL' >/dev/null
CREATE TABLE IF NOT EXISTS _lilian_migrations (
  filename TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SQL

APPLIED=0
SKIPPED=0
FAILED=0

for f in "${MIGRATIONS[@]}"; do
  base="$(basename "$f")"
  already=$(psql "$DB_URL" -tA -c "SELECT 1 FROM _lilian_migrations WHERE filename = '$base' LIMIT 1;" || echo "")
  if [[ "$already" == "1" ]]; then
    echo "[migrate] SKIP  $base (already applied)"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  echo "[migrate] APPLY $base"
  if psql "$DB_URL" -v ON_ERROR_STOP=1 -q -f "$f" >/dev/null; then
    psql "$DB_URL" -v ON_ERROR_STOP=1 -q -c "INSERT INTO _lilian_migrations (filename) VALUES ('$base');" >/dev/null
    APPLIED=$((APPLIED + 1))
  else
    echo "[migrate] FAILED $base" >&2
    FAILED=$((FAILED + 1))
    # Don't abort: leave the row un-inserted so the user can fix and retry.
  fi
done

echo "[migrate] Done. applied=$APPLIED skipped=$SKIPPED failed=$FAILED"
if [[ "$FAILED" -gt 0 ]]; then
  exit 1
fi
