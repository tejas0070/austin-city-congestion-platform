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
|---|------|--------|-------|
| 1 | Database without Row Level Security | ✅ N/A | No per-user/tenant data. Every row is public reference data; there is nothing to isolate between users. |
| 2 | Unprotected API routes (no auth) | ✅ By design | Endpoints are intentionally public and read-only (`GET` only). The real risk — abuse — is handled by rate limiting (#10). |
| 3 | Committed secrets (`.env` on GitHub) | ✅ Safe in git | `.env` is in `.gitignore` and **was never committed** (`git log --all -- .env` is empty; only `.env.example` is tracked). **Action required:** the real keys still need rotation — see below. |
| 4 | Broken access control (IDOR) | ✅ N/A | No object ownership and no IDs that reference per-user data. |
| 5 | Secret keys in frontend code | ✅ OK | Frontend holds only `REACT_APP_MAPBOX_TOKEN` (a *publishable* token, designed for client use) and the API base URL. No backend secrets reach the browser. Restrict the Mapbox token by URL in the Mapbox dashboard. |
| 6 | Server-Side Request Forgery (SSRF) | ✅ Not vulnerable | All outbound calls (Open-Meteo, TxDOT, Ticketmaster) use **hardcoded hosts**; no user input controls a URL host or path. |
| 7 | Missing CSRF protection | ✅ N/A | No cookies/sessions, no state-changing endpoints, `allow_credentials=False`. CSRF requires ambient credentials, which don't exist here. |
| 8 | Missing security headers | 🔧 **Fixed** | Added `SecurityHeadersMiddleware` (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, HSTS, COOP, CORP). |
| 9 | Wildcard CORS | ✅ Already correct | CORS is restricted to `localhost:3000/3001` + a `*.netlify.app` regex, `GET` only, no credentials. Not a wildcard. |
| 10 | No rate limiting | 🔧 **Fixed** | Added `RateLimitMiddleware` — per-IP fixed-window limiter (default 120 req/60s). |
| 11 | SQL injection | ✅ Not vulnerable | Web queries use the SQLAlchemy ORM (parameterized). The only raw SQL is in the admin-only `scripts/init_db.py`, on config-derived identifiers, never user input. |
| 12 | Cross-site scripting (XSS) | ✅ Not vulnerable | API returns JSON only; React escapes by default and there is no `dangerouslySetInnerHTML`/`innerHTML`. CSP (#8) adds defense-in-depth. |
| 13 | Unverified Stripe webhooks | ✅ N/A | No Stripe / no payments. |
| 14 | Insecure file uploads | ✅ N/A | No upload endpoints. |
| 15 | Verbose error messages | 🔧 **Fixed** | Added a global exception handler that logs detail server-side and returns a generic `500` to clients. Services already fail silently with safe fallbacks. |
| 16 | Weak password hashing | ✅ N/A | No passwords / no auth. |
| 17 | Hallucinated packages (slopsquatting) | ✅ Verified | All `requirements.txt` and `package.json` dependencies are real, well-known, pinned packages. |

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

### Deployment notes

- **Behind a proxy (Render/Railway/Netlify):** set `TRUST_PROXY=true` so the
  limiter keys on the real client IP from `X-Forwarded-For` instead of the proxy
  IP. Leave it `false` for local/direct runs (so the header can't be spoofed).
- **Multi-worker / multi-instance:** the limiter and cache are per-process. For a
  shared limit across workers, back them with Redis. For a single free-tier
  instance, the in-memory limiter is sufficient.

## ⚠️ Action required: rotate exposed API keys

The committed history is clean, but the live `.env` contains **real** keys that
should be treated as compromised and rotated (they were present in the working
tree and may have been shared/exposed):

| Key | Where to rotate | In use by code? |
|-----|-----------------|-----------------|
| `TICKETMASTER_API_KEY` | https://developer.ticketmaster.com (regenerate) | Yes — events |
| `DB_PASSWORD` (`Texas123`) | Rotate the Postgres role password | Yes — DB / docker-compose |
| `TOMTOM_API_KEY` | https://developer.tomtom.com | Yes — offline collector `scripts/collect_tomtom_observations.py` (not the live serving path). Rotate; keep it if you still collect training data, otherwise delete. |
| `OPENWEATHER_API_KEY` | https://openweathermap.org/api | **No** — no code reads it (weather uses keyless Open-Meteo); delete from `.env`. |

After rotating, also set a strong DB password (avoid `Texas123`-style values)
and confirm `.env` is never staged (`git status` should not list it).
