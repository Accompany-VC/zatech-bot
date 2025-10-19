"""CSP (Content Security Policy) management for the ZATech Bot admin dashboard."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

class CSPMiddleware(BaseHTTPMiddleware):
    """
    CSP Middleware for admin dashboard.
    
    *Only applies to /admin/* dashboard routes.*
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
        # CSP Policy
        self.csp_policy = (
            "default-src 'self'; "
            "script-src 'self' https://cdnjs.cloudflare.com; " # Allow CDN scripts
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https://*.firebaseapp.com https://*.googleapis.com; " # Firebase connections
            "img-src 'self' data:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Only apply CSP to admin routes
        if request.url.path == "/admin" or request.url.path.startswith("/admin/"):
            response.headers["Content-Security-Policy"] = self.csp_policy

        return response
