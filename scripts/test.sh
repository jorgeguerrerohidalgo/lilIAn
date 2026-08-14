#!/usr/bin/env bash
# ============================================
# scripts/test.sh - lilIAn test runner
# ============================================
# Runs the full test gauntlet for both backend and frontend.
# Designed to be safe to run repeatedly and from CI.
#
# Backend:
#   - ruff check + format --check
#   - pytest with coverage (terminates on first failure for speed)
# Frontend:
#   - next lint
#   - next build (catches type errors and compile-time issues)
#
# Usage:
#   bash scripts/test.sh
#   bash scripts/test.sh --backend-only
#   bash scripts/test.sh --frontend-only
#   bash scripts/test.sh --no-build    # skip next build (faster local loop)
# ============================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

BACKEND_ONLY=0
FRONTEND_ONLY=0
NO_BUILD=0
for arg in "$@"; do
  case "${arg}" in
    --backend-only)  BACKEND_ONLY=1 ;;
    --frontend-only) FRONTEND_ONLY=1 ;;
    --no-build)      NO_BUILD=1 ;;
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
info() { printf "\n${C_BOLD}[test]${C_RESET} %s\n" "$*"; }
ok()   { printf "${C_GREEN}[ok]${C_RESET}   %s\n" "$*"; }
warn() { printf "${C_YELLOW}[warn]${C_RESET} %s\n" "$*"; }
fail() { printf "${C_RED}[fail]${C_RESET} %s\n" "$*" >&2; }

# --- result tracking -------------------------------------------------
declare -a PHASES
declare -a PHASE_RESULTS
record() {
  PHASES+=("$1")
  PHASE_RESULTS+=("$2")
}

# --- backend ---------------------------------------------------------
BACKEND_DIR="${REPO_ROOT}/apps/backend"
if [ "${FRONTEND_ONLY}" -eq 0 ] && [ -d "${BACKEND_DIR}" ]; then
  info "Backend: pytest + ruff"

  if [ ! -d "${BACKEND_DIR}/venv" ] && [ ! -d "${BACKEND_DIR}/.venv" ]; then
    warn "Backend virtualenv missing at ${BACKEND_DIR}/venv."
    warn "Run: bash scripts/install.sh"
  fi

  # shellcheck disable=SC1091
  VENV_PATH=""
  if [ -d "${BACKEND_DIR}/venv" ]; then
    VENV_PATH="${BACKEND_DIR}/venv"
  elif [ -d "${BACKEND_DIR}/.venv" ]; then
    VENV_PATH="${BACKEND_DIR}/.venv"
  fi

  if [ -n "${VENV_PATH}" ]; then
    # shellcheck disable=SC1091
    source "${VENV_PATH}/bin/activate"
  fi

  pushd "${BACKEND_DIR}" >/dev/null

  if command -v ruff >/dev/null 2>&1; then
    info "Running ruff check"
    if ruff check .; then
      ok "ruff check passed"
    else
      fail "ruff check failed"
      record "backend:ruff" "FAIL"
      popd >/dev/null
      exit 1
    fi
    record "backend:ruff" "OK"
  else
    warn "ruff not installed; skipping static analysis."
  fi

  if command -v pytest >/dev/null 2>&1; then
    info "Running pytest with coverage"
    if pytest --cov=app --cov-report=term --cov-report=term-missing -q; then
      ok "pytest passed"
      record "backend:pytest" "OK"
    else
      fail "pytest failed"
      record "backend:pytest" "FAIL"
      popd >/dev/null
      exit 1
    fi
  else
    fail "pytest not installed. Run scripts/install.sh first."
    record "backend:pytest" "FAIL"
    popd >/dev/null
    exit 1
  fi

  popd >/dev/null
fi

# --- frontend --------------------------------------------------------
FRONTEND_DIR="${REPO_ROOT}/apps/frontend"
if [ "${BACKEND_ONLY}" -eq 0 ] && [ -d "${FRONTEND_DIR}" ]; then
  info "Frontend: lint + build"

  if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
    warn "frontend/node_modules missing."
    warn "Run: bash scripts/install.sh"
  fi

  pushd "${FRONTEND_DIR}" >/dev/null

  if [ -f package.json ] && command -v npm >/dev/null 2>&1; then
    info "Running npm run lint"
    if npm run lint; then
      ok "lint passed"
      record "frontend:lint" "OK"
    else
      fail "lint failed"
      record "frontend:lint" "FAIL"
      popd >/dev/null
      exit 1
    fi

    if [ "${NO_BUILD}" -eq 0 ]; then
      info "Running npm run build"
      if npm run build; then
        ok "build passed"
        record "frontend:build" "OK"
      else
        fail "build failed"
        record "frontend:build" "FAIL"
        popd >/dev/null
        exit 1
      fi
    else
      warn "Skipping build (--no-build)"
    fi
  else
    fail "npm not found or package.json missing."
    record "frontend:lint" "FAIL"
    popd >/dev/null
    exit 1
  fi

  popd >/dev/null
fi

# --- summary ---------------------------------------------------------
printf "\n"
info "Test summary"
printf "${C_DIM}-------------------------------------------------${C_RESET}\n"
for i in "${!PHASES[@]}"; do
  phase="${PHASES[$i]}"
  result="${PHASE_RESULTS[$i]}"
  if [ "${result}" = "OK" ]; then
    printf "  ${C_GREEN}OK${C_RESET}    %s\n" "${phase}"
  else
    printf "  ${C_RED}FAIL${C_RESET}  %s\n" "${phase}"
  fi
done
printf "${C_DIM}-------------------------------------------------${C_RESET}\n"

# exit non-zero if any phase failed
for r in "${PHASE_RESULTS[@]}"; do
  if [ "${r}" != "OK" ]; then
    exit 1
  fi
done
ok "All tests passed"
