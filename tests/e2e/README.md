# Lilian E2E Tests (Playwright)

End-to-end tests for the Lilian legal-AI platform. Each test creates a fresh user and matter via the FastAPI backend so the suite is self-contained and idempotent.

## Prerequisites

- Node.js + npm
- FastAPI backend running on `http://localhost:8000` (override with `E2E_API_URL`)
- Chromium installed via Playwright (`npx playwright install chromium`)

## Running

```bash
# from apps/frontend
npm run test:e2e            # headless
npm run test:e2e:headed     # visible browser
npm run test:e2e:ui         # Playwright UI
npm run test:e2e:report     # open HTML report
```

The suite expects the backend on `localhost:8000`. The Playwright config spins up `next dev` on port 3000 automatically; pass `E2E_NO_WEBSERVER=1` if you already have one running.

## Layout

```
e2e/
  fixtures/
    test-user.ts            # register/login helpers + storage-based auth
    sample.pdf              # minimal valid PDF used in upload tests
    sample-contract.txt     # Spanish contract for upload + analysis tests
  tests/
    01-login.spec.ts        # login happy path, bad password, auth redirect
    02-create-matter.spec.ts# create matter + validation
    03-upload-document.spec.ts# upload PDF + TXT, verify in list and via API
    04-view-analysis.spec.ts  # request analysis, wait for report, render UI
```

## Environment variables

| Var | Default | Purpose |
|-----|---------|---------|
| `E2E_BASE_URL` | `http://localhost:3000` | Frontend URL |
| `E2E_API_URL` | `http://localhost:8000` | Backend URL |
| `E2E_NO_WEBSERVER` | unset | Skip starting `next dev` if you already have one |
| `CI` | unset | Enables retries, list reporter, single worker |

## Notes

- The analysis tests can take up to 5 minutes per matter while the LLM pipeline runs.
- Tests use `localStorage.setItem("token", ...)` to skip the login form when only the post-login surface matters; the dedicated login test exercises the form itself.
- Tests do not clean up users or matters. Run against a disposable database in CI.