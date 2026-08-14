# Security Policy

## Supported Versions

The lilIAn project follows a phased support model. Security updates are
backported to the versions listed below.

| Version | Supported          | Status      |
|---------|--------------------|-------------|
| 2.1.x   | :white_check_mark: | Active dev  |
| 2.0.x   | :white_check_mark: | Maintenance |
| 1.x.x   | :x:                | End-of-life |
| < 1.0   | :x:                | End-of-life |

We commit to providing security fixes for the latest two minor releases
on the `main` branch. Older releases will receive Critical fixes only
for 90 days after the next minor release ships.

## Reporting a Vulnerability

**Please do NOT file public GitHub issues for security vulnerabilities.**

The lilIAn security team follows a coordinated disclosure process. To
report a vulnerability:

1. Email **security@lilian.example** (PGP key available on request).
2. Include a clear description of the issue, reproduction steps, and
   the impact you observed.
3. Allow up to 5 business days for an acknowledgment before escalating.

If you do not have an email channel available, open a GitHub issue
marked `security` and the maintainers will follow up to move the
conversation off-platform.

### What to Expect

| Stage                | Target Time           |
|----------------------|-----------------------|
| Initial ack          | 5 business days       |
| Triage + scope       | 10 business days      |
| Patch development    | 30-90 days (CVSS-based) |
| Public disclosure    | Coordinated with reporter |

We will keep you informed of progress. If we decline the report, we
will explain why.

## Response Timeline

Severity is scored using CVSS v3.1. Targets below assume the report
is accepted and reproducible.

| Severity    | CVSS     | First response | Target patch |
|-------------|----------|----------------|--------------|
| Critical    | >= 9.0   | 24 hours       | 7 days       |
| High        | 7.0-8.9  | 3 business days| 30 days      |
| Medium      | 4.0-6.9  | 5 business days| 90 days      |
| Low         | < 4.0    | 10 business days| Next release |

We may adjust timelines for complex issues that require schema
changes or coordinated upstream fixes. We will keep the reporter
informed.

## Disclosure Policy

We follow **coordinated disclosure**:

- The reporter agrees to keep the issue confidential until we publish
  a fix or 90 days have elapsed, whichever is shorter.
- We credit the reporter in the patch release notes unless they ask
  to remain anonymous.
- After the fix is published, we will publish a GHSA advisory with
  affected versions, severity, and mitigation steps.

We do not pursue legal action against researchers who follow this
policy and act in good faith.

## Security Features Implemented

The following controls are part of the current release.

### Authentication and Authorization

- Short-lived JWT access tokens with separate, longer-lived refresh
  tokens (FastAPI backend, `app/core/security.py`).
- bcrypt password hashing with direct bcrypt calls (passlib removed in
  S1-15 to avoid the `bcrypt.__about__` regression; see `requirements.txt`).
- Role-Based Access Control (RBAC) enforced at the API layer. See
  `docs/rbac-matrix.md` for the full matrix.
- Token blacklist backed by Redis for logout and forced revocation
  (`redis>=5.0.0`, `app/core/token_blacklist.py`).

### Transport and Headers

- HTTPS-only in production. See `DEPLOYMENT.md` and
  `render.yaml` for the TLS termination chain.
- Strict CORS allow-list via `ALLOWED_ORIGINS` (no wildcard in
  production).
- Backend sets `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, and
  `Referrer-Policy: strict-origin-when-cross-origin` by default.

### Input Validation

- All API payloads validated against Pydantic v2 schemas
  (`pydantic>=2.10.0`). No `Any` is accepted at trust boundaries.
- SQL injection prevented by SQLAlchemy 2.0 parameterized queries
  (`sqlalchemy==2.0.31`).
- File uploads validated against MIME type and size; the upload
  worker rejects binary mismatches before persistence.

### Rate Limiting

- `slowapi` rate limits on `/auth/register` and `/auth/login`
  (`slowapi==0.1.9`). See `app/api/v1/auth.py`.
- Per-IP and per-account limits; exponential backoff on repeated
  failures.

### Secrets Management

- All secrets read from environment variables. No secrets in source.
- Never commit `.env`, `.env.local`, `.env.production`, or
  `.env.*.local`. The `.gitignore` at the repo root enforces this.
- See `docs/SECRETS_MANAGEMENT.md` for the full rotation and
  provisioning procedure.

### Audit Logging

- Append-only audit log for security-relevant events (login, RBAC
  changes, matter access, document downloads). See
  `infra/supabase/migrations/007_create_audit_logs.sql`.
- Logged events include actor, target, action, timestamp, and
  source IP.

### Dependency Hygiene

- Pinned versions in `requirements.txt` and `package.json`/`package-lock.json`.
- Known vulnerable dependencies resolved:
  - **CVE-2024-33663 / CVE-2024-33664** (python-jose): upgraded to
    `python-jose[cryptography]>=3.4.0` (S1-14).
  - **CVE-2024-32661** (passlib / bcrypt truncation): passlib removed,
    bcrypt pinned to `>=4.2.1` (S1-15).
- CI runs `pip-audit` and `npm audit` on every PR. See
  `.github/workflows/`.

## Known Limitations

These are known gaps we are tracking. They are documented here so
deployers can make informed decisions.

- **No WAF in front of the API.** The production deploy assumes
  the platform (Render / Railway / Vercel) provides DDoS protection.
  Self-hosted deployments must add a reverse proxy with rate limiting.
- **No CSP on the frontend.** The Next.js app does not yet ship a
  Content Security Policy. Adding nonce-based CSP is tracked in
  S8 (see `ROADMAP_HARVEY_FEATURES.md`).
- **Audit logs are append-only at the application layer.** A
  database-level mechanism (e.g., partitioning + immutable role) is
  not yet configured.
- **No automatic secret rotation.** Operators must rotate
  `JWT_SECRET`, `ENCRYPTION_KEY`, and provider keys manually.
- **Email-based MFA is not implemented.** MFA is on the S8 roadmap
  but is not in the current release.

## Security Updates History

Each release below includes notable security changes. See the
GitHub Releases page for the full changelog.

### 2.1.0 (2026-08)

- S5 batch: accessibility hardening, ARIA labels on inputs and
  modals, `aria-busy` on async submit buttons.
- Added `role=alert` and `aria-live` regions to error and success
  messages.
- Removed `passlib` to avoid the bcrypt 4.2+ truncation regression
  (CVE-2024-32661). Backend now calls bcrypt directly.

### 2.0.0 (2026-07)

- Major rewrite: FastAPI 0.111, SQLAlchemy 2.0, Pydantic v2.
- Token blacklist added (Redis 5.0+).
- Rate limiting on `/auth/register` and `/auth/login` via `slowapi`.
- RBAC matrix formalized in `docs/rbac-matrix.md`.

### 1.0.0 (2026-03)

- Initial public release.

## Contact

For security issues: **security@lilian.example**

For general questions: open a GitHub issue at
<https://github.com/<org>/lilian/issues>.
