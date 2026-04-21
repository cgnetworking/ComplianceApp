from __future__ import annotations

import json
from functools import wraps

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from .authorization import has_any_portal_permission, portal_permissions_for_context
from .services.common import ValidationError, user_is_policy_reader

COMMON_SCRIPT_PATHS = (
    "js/portal_config.js",
    "js/api.js",
    "js/state.js",
    "js/accessibility.js",
    "js/shared.js",
)
PAGE_SCRIPT_PATHS = {
    "portal/index.html": ("js/controls.js", "js/policies.js", "js/reviews.js", "js/home.js"),
    "portal/controls.html": ("js/controls.js", "js/policies.js"),
    "portal/reviews.html": ("js/reviews.js",),
    "portal/review_tasks.html": ("js/reviews.js", "js/review_tasks.js"),
    "portal/audit_log.html": ("js/audit_log.js",),
    "portal/policies.html": ("js/controls.js", "js/policies.js"),
    "portal/risks.html": ("js/risks.js",),
    "portal/vendors.html": ("js/vendors.js",),
    "portal/assessments.html": ("js/assessments.js",),
}


def api_login_required(view_func):
    @wraps(view_func)
    def wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {
                    "detail": "Authentication required.",
                    "loginUrl": settings.LOGIN_URL,
                },
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return wrapped


def policy_reader_forbidden_response() -> JsonResponse:
    return JsonResponse(
        {
            "detail": "Policy Reader role can only access read-only policy state.",
        },
        status=403,
    )


def policy_reader_api_access(*, allow_policy_reader: bool):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args, **kwargs):
            if user_is_policy_reader(request.user) and not allow_policy_reader:
                return policy_reader_forbidden_response()
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def portal_api_forbidden_response(
    detail: str = "You do not have permission to access this resource.",
) -> JsonResponse:
    return JsonResponse({"detail": detail}, status=403)


def portal_page_permission_required(
    *requirements: tuple[str, str],
    detail: str = "Forbidden",
):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args, **kwargs):
            if not has_any_portal_permission(request.user, requirements):
                return HttpResponse(detail, status=403)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def portal_api_permission_required(
    *requirements: tuple[str, str],
    detail: str = "You do not have permission to access this resource.",
):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args, **kwargs):
            if not has_any_portal_permission(request.user, requirements):
                return portal_api_forbidden_response(detail)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def staff_page_required(view_func):
    @wraps(view_func)
    def wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponse("Forbidden", status=403)
        return view_func(request, *args, **kwargs)

    return wrapped


def staff_api_forbidden_response(detail: str = "Only staff users can access this resource.") -> JsonResponse:
    return JsonResponse({"detail": detail}, status=403)


def staff_api_access(view_func=None, *, detail: str = "Only staff users can access this resource."):
    def decorator(func):
        @wraps(func)
        def wrapped(request: HttpRequest, *args, **kwargs):
            if not request.user.is_staff:
                return staff_api_forbidden_response(detail)
            return func(request, *args, **kwargs)

        return wrapped

    if view_func is None:
        return decorator
    return decorator(view_func)


def current_user_context(request: HttpRequest) -> dict[str, object]:
    username = request.user.get_username() if request.user.is_authenticated else ""
    is_policy_reader = user_is_policy_reader(request.user)
    return {
        "username": username,
        "isStaff": bool(request.user.is_staff),
        "isPolicyReader": is_policy_reader,
        "portalPermissions": portal_permissions_for_context(request.user) if request.user.is_authenticated else {},
    }


def current_audit_actor(
    request: HttpRequest,
    *,
    error_cls: type[Exception] = ValidationError,
    message: str = "Authenticated portal actions require a username.",
) -> tuple[str, str]:
    username = request.user.get_username().strip() if request.user.is_authenticated else ""
    if not username:
        raise error_cls(message)
    display_name = request.user.get_full_name().strip() if request.user.is_authenticated else ""
    return username, display_name


def render_portal_page(
    request: HttpRequest,
    template_name: str,
    *,
    allow_policy_reader: bool = False,
) -> HttpResponse:
    return render(
        request,
        template_name,
        {
            "api_base_url": "/api",
            "login_url": settings.LOGIN_URL,
            "current_user": current_user_context(request),
            "common_scripts": COMMON_SCRIPT_PATHS,
            "page_scripts": PAGE_SCRIPT_PATHS.get(template_name, ()),
        },
    )


def parse_json_body(request: HttpRequest) -> object:
    try:
        return json.loads(request.body.decode("utf-8") or "null")
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValidationError("Invalid JSON body.") from error


def parse_json_body_or_400(request: HttpRequest) -> tuple[object | None, JsonResponse | None]:
    try:
        return parse_json_body(request), None
    except ValidationError as error:
        return None, JsonResponse({"detail": str(error)}, status=400)


__all__ = [
    "api_login_required",
    "portal_api_forbidden_response",
    "portal_page_permission_required",
    "portal_api_permission_required",
    "policy_reader_forbidden_response",
    "policy_reader_api_access",
    "staff_page_required",
    "staff_api_forbidden_response",
    "staff_api_access",
    "current_user_context",
    "current_audit_actor",
    "render_portal_page",
    "parse_json_body",
    "parse_json_body_or_400",
]
