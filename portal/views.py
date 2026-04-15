from __future__ import annotations

import json
from functools import wraps

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from .services import (
    ValidationError,
    create_review_checklist_item,
    create_uploaded_policies,
    create_vendor_responses,
    delete_review_checklist_item,
    delete_uploaded_policy,
    get_bootstrap_payload,
    get_mapping_payload,
    list_review_checklist_items,
    list_review_checklist_recommendations,
    normalize_control_state,
    normalize_mapping_payload,
    replace_mapping_payload,
    replace_risk_register,
    set_state_payload,
    update_review_state,
)


def safe_next_url(request: HttpRequest) -> str:
    candidate = request.POST.get("next") or request.GET.get("next") or settings.LOGIN_REDIRECT_URL
    if candidate in {settings.LOGIN_URL, settings.LOGOUT_REDIRECT_URL, "/logout/"}:
        return settings.LOGIN_REDIRECT_URL
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return settings.LOGIN_REDIRECT_URL


def sso_is_configured() -> bool:
    if settings.SOCIAL_AUTH_SSO_BACKEND_NAME == "oidc":
        return bool(
            getattr(settings, "SOCIAL_AUTH_OIDC_OIDC_ENDPOINT", "")
            and getattr(settings, "SOCIAL_AUTH_OIDC_KEY", "")
            and getattr(settings, "SOCIAL_AUTH_OIDC_SECRET", "")
        )
    return bool(settings.SOCIAL_AUTH_SSO_BACKEND_NAME)


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


def render_portal_page(request: HttpRequest, template_name: str) -> HttpResponse:
    return render(
        request,
        template_name,
        {
            "api_base_url": "/api",
            "login_url": settings.LOGIN_URL,
        },
    )


@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def login_page(request: HttpRequest) -> HttpResponse:
    next_url = safe_next_url(request)
    if request.user.is_authenticated:
        return redirect(next_url)

    form = AuthenticationForm(request=request, data=request.POST or None)
    form.fields["username"].widget.attrs.update({"autocomplete": "username"})
    form.fields["password"].widget.attrs.update({"autocomplete": "current-password"})
    if request.method == "POST" and request.POST.get("auth_mode") == "password":
        if form.is_valid():
            auth_login(request, form.get_user())
            return redirect(next_url)

    return render(
        request,
        "portal/login.html",
        {
            "form": form,
            "next_url": next_url,
            "sso_backend_name": settings.SOCIAL_AUTH_SSO_BACKEND_NAME,
            "sso_login_label": settings.SOCIAL_AUTH_SSO_LOGIN_LABEL,
            "sso_enabled": sso_is_configured(),
            "auth_error_message": request.GET.get("message", "").strip(),
        },
    )


@require_http_methods(["POST"])
def logout_view(request: HttpRequest) -> HttpResponse:
    auth_logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


@login_required(login_url="portal-login")
@ensure_csrf_cookie
def home_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/index.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
def controls_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/controls.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
def reports_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/reports.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
def reviews_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/reviews.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
def review_tasks_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/review_tasks.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
def audit_log_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/audit_log.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
def policies_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/policies.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
def risks_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/risks.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
def vendors_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/vendors.html")


def parse_json_body(request: HttpRequest) -> object:
    try:
        return json.loads(request.body.decode("utf-8") or "null")
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValidationError("Invalid JSON body.") from error


@api_login_required
@ensure_csrf_cookie
@require_GET
def bootstrap_state(request: HttpRequest) -> JsonResponse:
    return JsonResponse(get_bootstrap_payload())


@api_login_required
@require_http_methods(["POST"])
def upload_policies(request: HttpRequest) -> JsonResponse:
    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"detail": "Select at least one policy file to upload."}, status=400)

    try:
        documents, messages = create_uploaded_policies(files)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    return JsonResponse({"documents": documents, "messages": messages})


@api_login_required
@require_http_methods(["DELETE"])
def policy_document(request: HttpRequest, document_id: str) -> JsonResponse:
    try:
        deleted_document = delete_uploaded_policy(document_id)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)

    return JsonResponse({"deletedDocument": deleted_document})


@api_login_required
@require_http_methods(["POST"])
def upload_mapping(request: HttpRequest) -> JsonResponse:
    file_obj = request.FILES.get("file")
    if file_obj is None:
        files = request.FILES.getlist("files")
        file_obj = files[0] if files else None

    if file_obj is None:
        return JsonResponse({"detail": "Select a mapping file to upload."}, status=400)

    try:
        mapping_payload = replace_mapping_payload(file_obj)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    return JsonResponse({"mapping": mapping_payload})


@api_login_required
@require_http_methods(["POST"])
def upload_vendors(request: HttpRequest) -> JsonResponse:
    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"detail": "Select at least one vendor response file to import."}, status=400)

    responses = create_vendor_responses(files)
    return JsonResponse({"responses": responses})


@api_login_required
@require_http_methods(["GET", "PUT"])
def risk_register(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        payload = get_bootstrap_payload()
        return JsonResponse({"riskRegister": payload["riskRegister"]})

    body = parse_json_body(request)
    items = body.get("riskRegister") if isinstance(body, dict) and "riskRegister" in body else body

    try:
        risk_register_payload = replace_risk_register(items)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    return JsonResponse({"riskRegister": risk_register_payload})


@api_login_required
@require_http_methods(["GET", "POST"])
def checklist_items(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return JsonResponse({"checklistItems": list_review_checklist_items()})

    body = parse_json_body(request)
    payload = body.get("checklistItem") if isinstance(body, dict) and "checklistItem" in body else body

    try:
        checklist_item = create_review_checklist_item(payload)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    return JsonResponse({"checklistItem": checklist_item}, status=201)


@api_login_required
@require_http_methods(["DELETE"])
def checklist_item(request: HttpRequest, checklist_item_id: str) -> JsonResponse:
    try:
        deleted_checklist_item = delete_review_checklist_item(checklist_item_id)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)

    return JsonResponse({"deletedChecklistItem": deleted_checklist_item})


@api_login_required
@require_GET
def checklist_recommendations(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"recommendedChecklistItems": list_review_checklist_recommendations()})


@api_login_required
@require_http_methods(["GET", "PUT"])
def review_state(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        payload = get_bootstrap_payload()
        return JsonResponse({"reviewState": payload["reviewState"]})

    body = parse_json_body(request)
    payload = body.get("reviewState") if isinstance(body, dict) and "reviewState" in body else body
    username = request.user.get_username() if request.user.is_authenticated else "system"
    display_name = request.user.get_full_name() if request.user.is_authenticated else ""
    normalized = update_review_state(
        payload,
        actor_username=username or "system",
        actor_display_name=display_name.strip() or username or "System",
    )
    return JsonResponse({"reviewState": normalized})


@api_login_required
@require_http_methods(["GET", "PUT"])
def control_state(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        payload = get_bootstrap_payload()
        return JsonResponse({"controlState": payload["controlState"]})

    body = parse_json_body(request)
    payload = body.get("controlState") if isinstance(body, dict) and "controlState" in body else body
    normalized = normalize_control_state(payload)
    set_state_payload("control_state", normalized)
    return JsonResponse({"controlState": normalized})


@api_login_required
@require_http_methods(["GET", "PUT"])
def mapping_state(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return JsonResponse({"mapping": get_mapping_payload()})

    body = parse_json_body(request)
    payload = body.get("mapping") if isinstance(body, dict) and "mapping" in body else body
    normalized = normalize_mapping_payload(payload)
    set_state_payload("mapping_state", normalized)
    return JsonResponse({"mapping": normalized})
