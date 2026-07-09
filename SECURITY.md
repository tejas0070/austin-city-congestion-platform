# Security Audit & Hardening

This document records a security review of the Austin Traffic Intelligence
platform against a common vulnerability checklist, what was found, and what was
changed.

**Key context:** this is a **public, read-only data-visualization API**. There
are no user accounts, no login, no sessions/cookies, no payments, and no file
uploads. The backend serves public Austin traffic/weather/events data and the
frontend renders it on a map. That context makes most account-oriented
vulnerabilities not applicable — see the table.

## Audit results

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| 1 | Database without Row Level Security | ✅ N/A | No per-user/tenant data. Every row is public reference data; there is nothing to isolate between users. |
| 2 | Unprotected API routes (no auth) | ✅ By design | Endpoints are intentionally public and read-only (`GET` only). The real risk — abuse — is handled by rate limiting (#10). |
| 3 | Committed secrets (`.env` on GitHub) | ✅ Safe | `.env` and `.env.*` are in `.gitignore` and **were never committed** (`git log --all -- .env` is empty; only `.env.example` is tracked). All secrets are supplied at runtime via host environment variables. |
| 4 | Broken access control (IDOR) | ✅ N/A | No object ownership and no IDs that reference per-user data. |
| 5 | Secret keys in frontend code | ✅ OK | The map uses **MapLibre GL + Carto** basemaps, which need **no token**. The only build-time frontend variable is `REACT_APP_API_BASE_URL` (the public API URL). No backend secrets reach the browser. |
| 6 | Server-Side Request Forgery (SSRF) | ✅ Not vulnerable | All outbound calls (Open-Meteo, TomTom, Ticketmaster, Socrata) use **hardcoded hosts**; no user input controls a URL host or path. |
| 7 | Missing CSRF protection | ✅ N/A | No cookies/sessions, no state-changing endpoints, `allow_credentials=False`. CSRF requires ambient credentials, which don't exist here. |
| 8 | Missing security headers | 🔧 **Fixed** | `SecurityHeadersMiddleware` adds CSP (`default-src 'none'`), `X-Frame-Options: DENY`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS, COOP, and CORP to every response. |
| 9 | Wildcard CORS | ✅ Restricted | CORS allows `localhost:3000/3001` plus a regex for `*.netlify.app`, `*.vercel.app`, and `*.pages.dev`, `GET` only, no credentials. Extra origins (custom domains) are opt-in via `ALLOWED_ORIGINS`. Not a wildcard. |
| 10 | No rate limiting | 🔧 **Fixed** | `RateLimitMiddleware` — per-IP fixed-window limiter (default 120 req/60s), with a `TRUST_PROXY` guard so `X-Forwarded-For` is only honored behind a known proxy. |
| 11 | SQL injection | ✅ Not vulnerable | All DB access uses the SQLAlchemy ORM (parameterized). There is no raw SQL built from user input. |
| 12 | Cross-site scripting (XSS) | ✅ Not vulnerable | API returns JSON only; React escapes by default and there is no `dangerouslySetInnerHTML`/`innerHTML`. CSP (#8) adds defense-in-depth. |
| 13 | Unverified Stripe webhooks | ✅ N/A | No Stripe / no payments. |
| 14 | Insecure file uploads | ✅ N/A | No upload endpoints. |
| 15 | Verbose error messages | 🔧 **Fixed** | A global exception handler logs detail server-side and returns a generic `500` to clients. Route input errors return a clean `400`. Services fail silently with safe fallbacks. |
| 16 | Weak password hashing | ✅ N/A | No passwords / no auth. |
| 17 | Unbounded query parameters | ✅ Validated | Every query param is bounded (`Query(..., ge=…, le=…)`) and dates are parsed with a strict `YYYY-MM-DD` format that returns `400` on bad input. |
| 18 | Hallucinated packages (slopsquatting) | ✅ Verified | All `requirements.txt` and `package.json` dependencies are real, well-known, pinned packages. |

## Changes made (code)

- `backend/middleware/security_headers.py` — adds hardening headers to every
  response, including errors and CORS preflights.
- `backend/middleware/rate_limit.py` — per-IP fixed-window rate limiter.
  Configurable via env: `RATE_LIMIT_REQUESTS` (default 120),
  `RATE_LIMIT_WINDOW_SECONDS` (default 60), `TRUST_PROXY` (default false).
- `backend/main.py` — registers both middlewares in the correct order and adds a
  generic exception handler.

No new third-party dependencies were added; the limiter and headers use the
existing Starlette stack, matching the project's in-memory `utils/cache.py`
approach.

## Secret management

- **Nothing secret is committed.** `.env`/`.env.*` are git-ignored; only
  `.env.example` (placeholder values) is tracked. Confirm with
  `git log --all -- .env` (empty) and `git status` (never lists `.env`).
- **All secrets are runtime-only**, injected as host environment variables:
  Netlify (frontend build var `REACT_APP_API_BASE_URL`) and the Hugging Face
  Space / Render (`TOMTOM_API_KEY`, `TICKETMASTER_API_KEY`, `SOCRATA_APP_TOKEN`,
  and optionally `DATABASE_URL`). Every one is **optional** — without them the app
  runs on SQLite + committed model artifacts and silent fallbacks.
- **If a key is ever exposed, rotate it** at its provider and update the host
  environment variable. Never paste real keys into source, docs, or commit
  messages.

### Deployment notes

- **Behind a proxy (Hugging Face Space / Render / Netlify):** set
  `TRUST_PROXY=true` so the limiter keys on the real client IP from
  `X-Forwarded-For` instead of the proxy IP. Leave it `false` for local/direct
  runs (so the header can't be spoofed).
- **Multi-worker / multi-instance:** the limiter and cache are per-process. For a
  shared limit across workers, back them with Redis. For a single free-tier
  instance, the in-memory limiter is sufficient.
</content>
