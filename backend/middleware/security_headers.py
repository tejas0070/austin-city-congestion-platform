from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# This service returns only JSON; a locked-down CSP is appropriate because the
# API never serves HTML, scripts, or styles of its own. frame-ancestors 'none'
# blocks clickjacking; default-src 'none' means nothing loads if a response is
# ever mis-rendered as a document.
_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

# Static headers added to every response. HSTS is only honored over HTTPS, so it
# is harmless on local HTTP and active once deployed behind TLS (HF Space/Netlify).
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    # The frontend is a different origin (netlify.app); cross-origin lets it read
    # API responses while still opting out of the legacy no-CORS leak surface.
    "Cross-Origin-Resource-Policy": "cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": _CSP,
}

# Frozen view iterated per response; built once at import rather than each request.
_SECURITY_HEADER_ITEMS = tuple(_SECURITY_HEADERS.items())


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach hardening headers to every response, including error responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADER_ITEMS:
            response.headers.setdefault(header, value)
        return response
