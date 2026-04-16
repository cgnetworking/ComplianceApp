from __future__ import annotations

import base64
import secrets

from django.http import HttpRequest, HttpResponse


def _generate_csp_nonce() -> str:
    return base64.b64encode(secrets.token_bytes(16)).decode("ascii")


def csp_nonce_context(request: HttpRequest) -> dict[str, str]:
    nonce = getattr(request, "csp_nonce", "")
    return {"csp_nonce": nonce if isinstance(nonce, str) else ""}


class NonceContentSecurityPolicyMiddleware:
    """Attach a nonce-based CSP header to HTML responses without an explicit CSP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.csp_nonce = _generate_csp_nonce()
        response = self.get_response(request)

        if response.has_header("Content-Security-Policy"):
            return response

        content_type = str(response.get("Content-Type") or "").lower()
        if not content_type.startswith("text/html"):
            return response

        nonce = getattr(request, "csp_nonce", "")
        if not isinstance(nonce, str) or not nonce:
            return response

        response["Content-Security-Policy"] = (
            "default-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'self'; "
            "form-action 'self'; "
            f"script-src 'nonce-{nonce}' 'strict-dynamic'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "manifest-src 'self'; "
            "media-src 'self'; "
            "object-src 'none'; "
            "worker-src 'self'; "
            "frame-src 'self'"
        )
        return response
