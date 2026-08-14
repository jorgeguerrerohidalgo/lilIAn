#!/usr/bin/env bash
# ============================================
# scripts/setup-db.sh - lilIAn database setup
# ============================================
# Provisions the lilIAn database schema and (optionally) seed data.
#
# lilIAn ships SQL migrations in infra/supabase/migrations/ that are
# applied either via the Supabase dashboard or via psql. This script
# supports both flows:
#
#   1. Default: validates connectivity and prints the migration order.
#   2. --apply: applies every SQL file in numbered order via psql.
#      Requires DATABASE_URL to point to a writable Postgres instance.
#   3. --seed:  runs the optional post-migration data steps (e.g. the
#      add_legal_area backfill in apps/backend/migrations/).
#
# Usage:
#   bash scripts/setup-db.sh                 # dry-run, prints plan
#   bash scripts/setup-db.sh --apply         # apply via psql
#   bash scripts/setup-db.sh --seed          # apply + seed
#   bash scripts/setup-db.sh --check         # only TEST the connection
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

MIGRATIONS_DIR="${REPO_ROOT}/infra/supabase/migrations"
BACKEND_DIR="${REPO_ROOT}/apps/backend"

APPLY=0
SEED=0
CHECK_ONLY=0
for arg in "$@"; do
  case "${arg}" in
    --apply)  APPLY=1 ;;
    --seed)   SEED=1 ;;
    --check)  CHECK_ONLY=1 ;;
    -h|--help)
      sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      exit 2
      ;;
  esac
done

# --- pretty printing -------------------------------------------------
if [ -t 1 ]; then
  C_BOLD="\033[1m"; C_DIM="\033[2m"; C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"; C_RESET="\033[0m"
else
  C_BOLD=""; C_DIM=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_RESET=""
fi
info() { printf "\n${C_BOLD}[setup-db]${C_RESET} %s\n" "$*"; }
ok()   { printf "${C_GREEN}[ok]${C_RESET}      %s\n" "$*"; }
warn() { printf "${C_YELLOW}[warn]${C_RESET}    %s\n" "$*"; }
fail() { printf "${C_RED}[fail]${C_RESET}    %s\n" "$*" >&2; }

# --- preflight -------------------------------------------------------
info "lilIAn database setup"
printf "${C_DIM}Repo root: %s${C_RESET}\n" "${REPO_ROOT}"

if [ ! -d "${MIGRATIONS_DIR}" ]; then
  fail "Migrations directory not found: ${MIGRATIONS_DIR}"
  exit 1
fi

# Sort SQL files by leading numeric prefix (001, 002, ...).
mapfile -t MIGRATIONS < <(find "${MIGRATIONS_DIR}" -maxdepth 1 -type f -name '*.sql' | sort)
if [ "${#MIGRATIONS[@]}" -eq 0 ]; then
  fail "No .sql files found in ${MIGRATIONS_DIR}"
  exit 1
fi

info "Found ${#MIGRATIONS[@]} migration files"
for m in "${MIGRATIONS[@]}"; do
  printf "  - %s\n" "$(basename "${m}")"
done

# --- check DATABASE_URL ----------------------------------------------
if [ -z "${DATABASE_URL:-}" ]; then
  # Try to load from .env files in priority order.
  for env_file in "${REPO_ROOT}/.env" "${BACKEND_DIR}/.env"; do
    if [ -f "${env_file}" ]; then
      # shellcheck disable=SC1090
      DATABASE_URL="$(grep -E '^DATABASE_URL=' "${env_file}" | head -1 | cut -d= -f2-)"
      if [ -n "${DATABASE_URL}" ]; then
        info "Loaded DATABASE_URL from ${env_file}"
        break
      fi
    fi
  done
fi

if [ -z "${DATABASE_URL:-}" ]; then
  warn "DATABASE_URL not set. Cannot validate connection or apply migrations."
  warn "Set it in .env or export it before running this script."
fi

# --- connection check -----------------------------------------------
if [ -n "${DATABASE_URL:-}" ]; then
  if command -v psql >/dev/null 2>&1; then
    info "Testing connection..."
    if psql "${DATABASE_URL}" -c 'SELECT 1;' >/dev/null 2>&1; then
      ok "Database connection succeeded"
    else
      fail "Database connection failed"
      if [ "${CHECK_ONLY}" -eq 1 ]; then exit 1; fi
      if [ "${APPLY}" -eq 1 ]; then
        fail "Refusing to apply migrations without a working connection."
        exit 1
      fi
    fi
  else
    warn "psql not installed; skipping connectivity test."
    if [ "${APPLY}" -eq 1 ]; then
      fail "psql is required for --apply. Install postgresql-client."
      exit 1
    fi
  fi
fi

[ "${CHECK_ONLY}" -eq 1 ] && exit 0

# --- apply migrations -----------------------------------------------
if [ "${APPLY}" -eq 1 ]; then
  if [ -z "${DATABASE_URL:-}" ]; then
    fail "DATABASE_URL is required for --apply."
    exit 1
  fi
  if ! command -v psql >/dev/null 2>&1; then
    fail "psql not installed. Install postgresql-client (e.g. apt install postgresql-client)."
    exit 1
  fi

  info "Applying migrations in order"
  for m in "${MIGRATIONS[@]}"; do
    name="$(basename "${m}")"
    printf "  -> %s ... " "${name}"
    if psql "${DATABASE_URL}" --set ON_ERROR_STOP=0 -v ON_ERROR_STOP=0 -f "${m}" >/dev/null 2>&1; then
      printf "${C_GREEN}ok${C_RESET}\n"
    else
      # ON_ERROR_STOP=0 keeps going on already-applied tables — common
      # when re-running setup.
      printf "${C_YELLOW}skipped (already applied or non-fatal)${C_RESET}\n"
    fi
  done
  ok "Migrations applied"
fi

# --- seed data ------------------------------------------------------
if [ "${SEED}" -eq 1 ]; then
  info "Running seed: backfill legal_area on existing chunks"
  if [ -d "${BACKEND_DIR}/venv" ]; then
    # shellcheck disable=SC1091
    source "${BACKEND_DIR}/venv/bin/activate"
  fi
  if [ -f "${BACKEND_DIR}/migrations/add_legal_area.py" ]; then
    pushd "${BACKEND_DIR}" >/dev/null
    if python -m migrations.add_legal_area; then
      ok "Seed step completed"
    else
      fail "Seed step failed"
      popd >/dev/null
      exit 1
    fi
    popd >/dev/null
  else
    warn "No seed script found at ${BACKEND_DIR}/migrations/"
  fi
fi

# --- summary --------------------------------------------------------
if [ "${APPLY}" -eq 0 ] && [ "${SEED}" -eq 0 ]; then
  printf "\n"
  info "Dry-run complete. No changes applied."
  printf "${C_DIM}Next steps:${C_RESET}\n"
  printf "  - Run with --apply to apply migrations via psql.\n"
  printf "  - Or apply them from the Supabase SQL editor.\n"
  printf "  - Run with --seed after --apply to backfill legal_area.\n"
else
  printf "\n"
  ok "Database setup complete"
fi
