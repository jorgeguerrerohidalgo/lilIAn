#!/usr/bin/env bash
# ============================================
# scripts/install.sh - lilIAn local installer
# ============================================
# Provisions a fresh checkout:
#   1. Verifies Python 3.11+ and Node 20+ are present.
#   2. Creates a Python virtualenv for the backend and installs
#      requirements.txt.
#   3. Installs frontend dependencies via npm.
#   4. Copies .env.example files to .env where missing.
#   5. Prints a summary of next steps.
#
# Usage:
#   bash scripts/install.sh
#   bash scripts/install.sh --skip-frontend
#   bash scripts/install.sh --skip-backend
# ============================================
set -euo pipefail

# Resolve repo root from the script location, regardless of cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# --- argument parsing ------------------------------------------------
SKIP_BACKEND=0
SKIP_FRONTEND=0
SKIP_ENV=0
for arg in "$@"; do
  case "${arg}" in
    --skip-backend)  SKIP_BACKEND=1 ;;
    --skip-frontend) SKIP_FRONTEND=1 ;;
    --skip-env)      SKIP_ENV=1 ;;
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
info()    { printf "${C_BOLD}[install]${C_RESET} %s\n" "$*"; }
ok()      { printf "${C_GREEN}[ok]${C_RESET}      %s\n" "$*"; }
warn()    { printf "${C_YELLOW}[warn]${C_RESET}    %s\n" "$*"; }
fail()    { printf "${C_RED}[fail]${C_RESET}    %s\n" "$*" >&2; }

# --- helper functions -----------------------------------------------
require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command not found: $1"
    return 1
  fi
}

version_gte() {
  # version_gte <have> <want>  -> exits 0 if have >= want
  local have="$1" want="$2"
  local h_major h_minor w_major w_minor
  h_major="$(echo "${have}" | cut -d. -f1)"
  h_minor="$(echo "${have}" | cut -d. -f2)"
  w_major="$(echo "${want}" | cut -d. -f1)"
  w_minor="$(echo "${want}" | cut -d. -f2)"
  if [ "${h_major}" -gt "${w_major}" ]; then return 0; fi
  if [ "${h_major}" -lt "${w_major}" ]; then return 1; fi
  [ "${h_minor}" -ge "${w_minor}" ]
}

# --- preflight -------------------------------------------------------
info "lilIAn installer"
printf "${C_DIM}Repo root: %s${C_RESET}\n" "${REPO_ROOT}"

require_cmd python3 || { fail "Install Python 3.11+ first."; exit 1; }
require_cmd node    || { fail "Install Node.js 20+ first."; exit 1; }

PY_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
NODE_VERSION="$(node -p 'process.versions.node')"
NODE_MAJOR="$(echo "${NODE_VERSION}" | cut -d. -f1)"

if ! version_gte "${PY_VERSION}" "3.11"; then
  fail "Python ${PY_VERSION} found; lilIAn requires 3.11+."
  exit 1
fi
ok "Python ${PY_VERSION}"

if [ "${NODE_MAJOR}" -lt 20 ]; then
  fail "Node ${NODE_VERSION} found; lilIAn requires 20+."
  exit 1
fi
ok "Node ${NODE_VERSION}"

# --- backend ---------------------------------------------------------
if [ "${SKIP_BACKEND}" -eq 0 ]; then
  info "Setting up backend (FastAPI)..."
  pushd "${REPO_ROOT}/apps/backend" >/dev/null

  VENV_DIR="venv"
  if [ ! -d "${VENV_DIR}" ]; then
    info "Creating virtualenv at ${VENV_DIR}/"
    python3 -m venv "${VENV_DIR}"
  else
    info "Reusing existing virtualenv at ${VENV_DIR}/"
  fi

  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  python -m pip install --upgrade pip wheel >/dev/null
  info "Installing requirements.txt"
  pip install -r requirements.txt
  ok "Backend installed"

  popd >/dev/null
else
  warn "Skipping backend (--skip-backend)"
fi

# --- frontend --------------------------------------------------------
if [ "${SKIP_FRONTEND}" -eq 0 ]; then
  info "Setting up frontend (Next.js)..."
  pushd "${REPO_ROOT}/apps/frontend" >/dev/null

  if [ ! -f package.json ]; then
    fail "frontend/package.json missing — aborting."
    exit 1
  fi

  if command -v npm >/dev/null 2>&1; then
    info "Running npm install"
    npm install
    ok "Frontend installed (npm)"
  else
    fail "npm not found. Install Node.js 20+ to get npm."
    exit 1
  fi

  popd >/dev/null
else
  warn "Skipping frontend (--skip-frontend)"
fi

# --- env files -------------------------------------------------------
if [ "${SKIP_ENV}" -eq 0 ]; then
  info "Copying .env.example -> .env where missing"
  for example_file in "${REPO_ROOT}/.env.example" "${REPO_ROOT}/apps/backend/.env.example"; do
    if [ -f "${example_file}" ]; then
      target="${example_file%.example}"
      if [ -f "${target}" ]; then
        warn "Existing ${target} found; leaving untouched."
      else
        cp "${example_file}" "${target}"
        ok "Created ${target}"
      fi
    fi
  done
  warn "Edit .env files now to add real credentials (Supabase, JWT_SECRET, LLM_API_KEY...)."
else
  warn "Skipping env files (--skip-env)"
fi

# --- summary ---------------------------------------------------------
printf "\n"
info "Install complete."
printf "${C_DIM}Next steps:${C_RESET}\n"
printf "  1. Edit %s and %s with real values.\n" "${REPO_ROOT}/.env" "${REPO_ROOT}/apps/backend/.env"
printf "  2. Run the database setup:    bash scripts/setup-db.sh\n"
printf "  3. Start the dev stack:       docker compose up --build\n"
printf "  4. Or run components directly:\n"
printf "       backend:  cd apps/backend && source venv/bin/activate && uvicorn app.main:app --reload\n"
printf "       frontend: cd apps/frontend && npm run dev\n"
