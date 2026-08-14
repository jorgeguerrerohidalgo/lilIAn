# Contributing to lilIAn

Thank you for your interest in contributing to **lilIAn**, the legal AI platform.
We welcome bug reports, feature suggestions, documentation improvements, and code
contributions from the community.

By participating in this project you agree to abide by our
[Code of Conduct](./CODE_OF_CONDUCT.md).

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [How to Report a Bug](#how-to-report-a-bug)
3. [How to Suggest a Feature](#how-to-suggest-a-feature)
4. [Development Setup](#development-setup)
5. [Development Workflow](#development-workflow)
6. [Code Style](#code-style)
7. [Testing Requirements](#testing-requirements)
8. [Pull Request Process](#pull-request-process)
9. [Security Reporting](#security-reporting)
10. [Getting Help](#getting-help)

---

## Code of Conduct

This project follows the [Contributor Covenant](./CODE_OF_CONDUCT.md). All
participants — maintainers, contributors, and users — are expected to treat
each other with respect. Instances of abusive, harassing, or otherwise
unacceptable behavior may be reported to the project maintainers (see
`SECURITY.md` for the reporting channel).

---

## How to Report a Bug

Bugs are tracked as GitHub issues. Use the **Bug Report** template when
opening a new issue.

A good bug report should include:

- A clear, descriptive title.
- Exact steps to reproduce the issue.
- The behavior you expected and what actually happened.
- Screenshots, logs, stack traces, or screen recordings where helpful.
- The environment where you observed the bug (OS, browser, Node / Python
  version, relevant configuration).
- Anything else that helps us narrow it down.

Before opening an issue, search the existing issue list to make sure the bug
has not already been reported.

## How to Suggest a Feature

Feature requests are tracked as GitHub issues using the **Feature Request**
template. A strong proposal explains:

- The problem you are trying to solve and why it matters.
- The proposed solution at a high level.
- Alternatives you considered and why they were rejected.
- Mockups, wireframes, or screenshots when the change is user-facing.
- Acceptance criteria that define "done".

Larger architectural changes should be discussed in an issue **before**
opening a pull request so we can align on the direction and avoid wasted
work.

---

## Development Setup

### Prerequisites

| Tool   | Version (minimum) | Notes                                      |
|--------|-------------------|--------------------------------------------|
| Python | 3.11+             | Backend, document processor worker         |
| Node   | 20+               | Frontend (Next.js 14)                      |
| Git    | 2.30+             | Required for conventional-commit hooks     |
| Docker | 24+               | Optional, for local stack via docker-compose |

### Clone & install

```bash
git clone https://github.com/<org>/lilian.git
cd lilian

# Backend
cd apps/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### Environment variables

Copy the example files and fill in the values you need:

```bash
cp apps/backend/.env.example apps/backend/.env
cp apps/frontend/.env.local.example apps/frontend/.env.local   # if present
```

See `docs/SECRETS_MANAGEMENT.md` for the full list of secrets and the
recommended rotation cadence. **Never commit real secrets.**

### Run the local stack

```bash
# Backend (FastAPI)
cd apps/backend
uvicorn app.main:app --reload

# Frontend (Next.js)
cd apps/frontend
npm run dev
```

`docker-compose.yml` at the repo root boots the full stack (Postgres,
Redis, backend, frontend, worker) for integration testing.

---

## Development Workflow

### Branching

- Branch off `main`.
- Use the prefix `feature/`, `fix/`, `refactor/`, `docs/`, or `chore/`.
- Keep branches short-lived and focused on a single concern.

### Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

<optional body>
<optional footer>
```

Allowed types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`,
`ci`. The scope is the affected module (e.g. `backend`, `frontend`, `auth`,
`docs`).

Attribution via `Co-Authored-By:` trailers is disabled globally for this
project.

### Pre-commit checks

Before opening a PR, run the local equivalents of CI locally:

```bash
# Backend
cd apps/backend
ruff check .
pytest

# Frontend
cd apps/frontend
npm run lint
npm run build
```

---

## Code Style

### Python (backend, document processor)

- **Formatter / linter**: [Ruff](https://docs.astral.sh/ruff/) (see
  `apps/backend/pyproject.toml`).
- Line length: 100.
- Target version: Python 3.12.
- Type hints on all public functions.
- Prefer immutable data structures.
- Avoid `print()`; use the project logger (`logging.getLogger(__name__)`).

### TypeScript / React (frontend)

- **Formatter**: Prettier (Next.js default config).
- **Linter**: ESLint via `eslint-config-next`.
- TypeScript strict mode is required.
- Components live under `apps/frontend/components/<feature>/`.
- Use the existing UI primitives in `components/ui/` before reaching for a
  new dependency.

### Imports

Group imports in three blocks (standard library, third-party, local) and
sort each block alphabetically.

### Error handling

- Catch errors at boundaries; do not swallow them silently.
- Use user-friendly messages on UI-facing code.
- Log detailed context (request id, user id, stack) on the server side.

---

## Testing Requirements

- **Minimum coverage**: 80% (project target; per-package coverage may be
  higher — see `apps/backend/pyproject.toml` for the current floor).
- **Test types required**: unit, integration, and E2E where applicable.
- **Pattern**: AAA (Arrange / Act / Assert) — see the existing tests for
  examples.
- **Naming**: `test_<unit>_<behavior>.py` for files; descriptive test
  function names that explain the expected behavior.

### Where tests live

| Module                     | Test path                                       |
|----------------------------|-------------------------------------------------|
| Backend (FastAPI)          | `apps/backend/tests/`                           |
| Frontend unit / component  | co-located as `*.test.tsx` next to the file     |
| Frontend E2E (Playwright)  | `apps/frontend/e2e/`                            |
| Document processor worker  | `workers/document_processor/tests/`             |

### TDD

For new features, write the test first, see it fail (RED), implement the
minimum code to pass (GREEN), then refactor (IMPROVE).

---

## Pull Request Process

1. **Open or link an issue.** PRs without a tracked issue are unlikely to
   be accepted.
2. **Use the PR template.** Fill in the type of change, the related
   issue, the testing performed, and the checklist.
3. **Keep PRs focused.** One concern per PR. Split unrelated refactors
   into separate PRs.
4. **Pass CI.** All checks (`lint-python`, `lint-frontend`,
   `test-backend`, `build-backend`, `build-frontend`) must be green
   before review.
5. **Request review** from the appropriate code owner (see
   `.github/CODEOWNERS`). At least one approving review is required.
6. **Squash-merge** is the default. Keep the commit history on `main`
   linear and readable.
7. After merge, delete the source branch.

### Review expectations

- Reviews are best-effort. Expect feedback within a few business days.
- Address every comment, or reply with a reason for not addressing it.
- Force-pushes are discouraged after the first review to keep the review
  thread readable.

---

## Security Reporting

**Do not open public GitHub issues for security vulnerabilities.** Use the
private reporting channel described in `SECURITY.md` (link to be added
when the file exists; otherwise contact the maintainers directly).

We aim to acknowledge reports within 2 business days.

---

## Getting Help

- Open a GitHub issue with the `question` label.
- Check existing documentation under `docs/`.
- Reach the maintainers via the contact channel listed in `README.md`.

Thanks again for contributing to lilIAn.
