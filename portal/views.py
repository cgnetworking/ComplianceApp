from __future__ import annotations

import ipaddress
import math
import time

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from .authorization import (
    PAGE_PERMISSION_REQUIREMENTS,
    PortalAction,
    PortalResource,
    has_any_portal_permission,
    has_portal_permission,
)
from .services.bootstrap import (
    append_portal_audit_entry,
    audit_log_payload_for_viewer,
    create_review_checklist_item,
    delete_review_checklist_item,
    get_bootstrap_payload,
    review_state_payload_for_viewer,
    update_review_state,
)
from .services.common import ValidationError, normalize_control_state, normalize_mapping_payload, set_state_payload
from .services.mapping import replace_mapping_payload
from .services.policies import (
    approve_uploaded_policy,
    create_uploaded_policies,
    create_vendor_responses,
    delete_uploaded_policy,
    delete_vendor_response,
    get_policy_document,
    list_vendor_responses,
    update_uploaded_policy_approver,
)
from .services.risks import (
    create_risk_record,
    delete_risk_record,
    list_risk_register,
    replace_risk_register,
    update_risk_record,
)
from .services.uploads import (
    validate_mapping_upload_file,
    validate_policy_upload_files,
    validate_vendor_upload_files,
)
from .view_helpers import (
    api_login_required,
    current_audit_actor,
    parse_json_body_or_400,
    portal_api_forbidden_response,
    portal_page_permission_required,
    render_portal_page,
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
            settings.SOCIAL_AUTH_OIDC_OIDC_ENDPOINT
            and settings.SOCIAL_AUTH_OIDC_KEY
            and settings.SOCIAL_AUTH_OIDC_SECRET
        )
    return bool(settings.SOCIAL_AUTH_SSO_BACKEND_NAME)


def normalized_ip_address(value: object) -> str:
    normalized = str(value or "").split(",", 1)[0].strip()
    if not normalized:
        return ""
    try:
        return ipaddress.ip_address(normalized).compressed
    except ValueError:
        return ""


def request_client_ip(request: HttpRequest) -> str:
    remote_addr = normalized_ip_address(request.META.get("REMOTE_ADDR"))
    trusted_proxy_ips = {
        normalized_ip_address(value)
        for value in settings.TRUSTED_PROXY_IPS
        if normalized_ip_address(value)
    }
    if remote_addr and remote_addr in trusted_proxy_ips:
        real_ip = normalized_ip_address(request.META.get("HTTP_X_REAL_IP"))
        if real_ip:
            return real_ip
    if not remote_addr:
        raise ValidationError("Request client IP address is unavailable.")
    return remote_addr


def normalized_login_username(raw_username: object) -> str:
    return str(raw_username or "").strip().lower()


def login_throttle_cache_key(*, username: str, client_ip: str, kind: str) -> str:
    safe_username = normalized_login_username(username) or "anonymous"
    safe_ip = client_ip or "unknown"
    return f"portal:auth:{kind}:{safe_username}:{safe_ip}"


def login_lockout_remaining_seconds(*, username: str, client_ip: str) -> int:
    lockout_key = login_throttle_cache_key(username=username, client_ip=client_ip, kind="lockout")
    lockout_until = cache.get(lockout_key)
    if not isinstance(lockout_until, (int, float)):
        return 0
    remaining_seconds = int(lockout_until - time.time())
    if remaining_seconds <= 0:
        cache.delete(lockout_key)
        return 0
    return remaining_seconds


def clear_login_throttle(*, username: str, client_ip: str) -> None:
    cache.delete_many(
        [
            login_throttle_cache_key(username=username, client_ip=client_ip, kind="attempts"),
            login_throttle_cache_key(username=username, client_ip=client_ip, kind="lockout"),
        ]
    )


def register_failed_login_attempt(*, username: str, client_ip: str) -> tuple[int, int]:
    max_attempts = int(settings.LOGIN_THROTTLE_MAX_ATTEMPTS)
    window_seconds = int(settings.LOGIN_THROTTLE_WINDOW_SECONDS)
    lockout_seconds = int(settings.LOGIN_THROTTLE_LOCKOUT_SECONDS)
    attempts_key = login_throttle_cache_key(username=username, client_ip=client_ip, kind="attempts")
    lockout_key = login_throttle_cache_key(username=username, client_ip=client_ip, kind="lockout")

    attempts = int(cache.get(attempts_key, 0)) + 1
    cache.set(attempts_key, attempts, timeout=window_seconds)
    if attempts >= max_attempts:
        lockout_until = time.time() + lockout_seconds
        cache.set(lockout_key, lockout_until, timeout=lockout_seconds)
        cache.delete(attempts_key)
        return attempts, lockout_seconds
    return attempts, 0


def audit_failed_login_attempt(
    request: HttpRequest,
    *,
    username: str,
    reason: str,
    attempt_count: int,
    lockout_remaining_seconds: int,
) -> None:
    client_ip = request_client_ip(request)
    normalized_username = normalized_login_username(username)
    actor_username = normalized_username or "anonymous"
    if reason == "lockout":
        summary = f"Blocked password login for {normalized_username or 'anonymous'} during lockout."
    else:
        summary = f"Failed password login for {normalized_username or 'anonymous'}."

    append_portal_audit_entry(
        action="failed_login",
        entity_type="authentication",
        entity_id=normalized_username or client_ip,
        summary=summary,
        actor_username=actor_username,
        actor_display_name=normalized_username or "Anonymous",
        metadata={
            "source": "auth",
            "authMode": "password",
            "reason": reason,
            "usernameAttempted": normalized_username,
            "clientIp": client_ip,
            "attemptCount": attempt_count,
            "lockoutRemainingSeconds": max(lockout_remaining_seconds, 0),
        },
    )


def named_item_preview(items: list[object], *, limit: int = 3) -> str:
    names: list[str] = []
    for item in items:
        name = str(item or "").strip()
        if not name:
            continue
        names.append(name)
    if not names:
        return ""
    preview = ", ".join(names[:limit])
    if len(names) > limit:
        preview = f"{preview}, +{len(names) - limit} more"
    return preview


def page_permission_detail(page_label: str) -> str:
    return f"You do not have permission to access the {page_label} page."


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
        username_attempt = str(request.POST.get("username") or "")
        client_ip = request_client_ip(request)
        lockout_remaining = login_lockout_remaining_seconds(username=username_attempt, client_ip=client_ip)
        if lockout_remaining > 0:
            retry_minutes = max(1, math.ceil(lockout_remaining / 60))
            form.add_error(None, f"Too many failed sign-in attempts. Try again in {retry_minutes} minute(s).")
            audit_failed_login_attempt(
                request,
                username=username_attempt,
                reason="lockout",
                attempt_count=0,
                lockout_remaining_seconds=lockout_remaining,
            )
        elif form.is_valid():
            clear_login_throttle(username=username_attempt, client_ip=client_ip)
            auth_login(request, form.get_user())
            return redirect(next_url)
        else:
            attempt_count, lockout_seconds = register_failed_login_attempt(username=username_attempt, client_ip=client_ip)
            if lockout_seconds > 0:
                retry_minutes = max(1, math.ceil(lockout_seconds / 60))
                form.add_error(None, f"Too many failed sign-in attempts. Try again in {retry_minutes} minute(s).")
            audit_failed_login_attempt(
                request,
                username=username_attempt,
                reason="invalid_credentials",
                attempt_count=attempt_count,
                lockout_remaining_seconds=lockout_seconds,
            )

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
@portal_page_permission_required(*PAGE_PERMISSION_REQUIREMENTS["home"])
def home_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/index.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
@portal_page_permission_required(*PAGE_PERMISSION_REQUIREMENTS["controls"])
def controls_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/controls.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
@portal_page_permission_required(*PAGE_PERMISSION_REQUIREMENTS["reviews"])
def reviews_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/reviews.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
@portal_page_permission_required(*PAGE_PERMISSION_REQUIREMENTS["review-tasks"])
def review_tasks_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/review_tasks.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
@portal_page_permission_required(*PAGE_PERMISSION_REQUIREMENTS["audit-log"])
def audit_log_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/audit_log.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
@portal_page_permission_required(*PAGE_PERMISSION_REQUIREMENTS["policies"])
def policies_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/policies.html", allow_policy_reader=True)


@login_required(login_url="portal-login")
@ensure_csrf_cookie
@portal_page_permission_required(*PAGE_PERMISSION_REQUIREMENTS["risks"])
def risks_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/risks.html")


@login_required(login_url="portal-login")
@ensure_csrf_cookie
@portal_page_permission_required(*PAGE_PERMISSION_REQUIREMENTS["vendors"])
def vendors_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/vendors.html")


@api_login_required
@ensure_csrf_cookie
@require_GET
def bootstrap_state(request: HttpRequest) -> JsonResponse:
    page = str(request.GET.get("page") or "").strip().lower()
    page_requirements = PAGE_PERMISSION_REQUIREMENTS.get(page)
    if page_requirements and not has_any_portal_permission(request.user, page_requirements):
        return portal_api_forbidden_response(page_permission_detail(page.replace("-", " ")))
    return JsonResponse(
        get_bootstrap_payload(
            viewer=request.user,
            page=page,
        )
    )


@api_login_required
@require_http_methods(["POST"])
def upload_policies(request: HttpRequest) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.POLICY_DOCUMENT, PortalAction.ADD):
        return portal_api_forbidden_response("You do not have permission to upload policy documents.")
    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"detail": "Select at least one policy file to upload."}, status=400)

    try:
        validate_policy_upload_files(files)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    try:
        documents, messages = create_uploaded_policies(files)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    actor_username, actor_display_name = current_audit_actor(request)
    imported_file_names = [str(getattr(file, "name", "") or "").strip() for file in files]
    imported_file_preview = named_item_preview(imported_file_names)
    append_portal_audit_entry(
        action="import_policy_documents",
        entity_type="policy",
        entity_id=f"{len(documents)}",
        summary=(
            f"Imported policy file{'s' if len(imported_file_names) != 1 else ''}: {imported_file_preview}."
            if imported_file_preview
            else f"Imported {len(documents)} policy document{'s' if len(documents) != 1 else ''}."
        ),
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "policies",
            "importType": "policy_upload",
            "documentCount": len(documents),
            "documentIds": [str(item.get("id") or "") for item in documents if isinstance(item, dict)],
            "fileNames": imported_file_names,
            "messages": messages,
        },
    )

    return JsonResponse({"documents": documents, "messages": messages})


@api_login_required
@require_http_methods(["GET", "DELETE"])
def policy_document(request: HttpRequest, document_id: str) -> JsonResponse:
    if request.method == "GET":
        try:
            document = get_policy_document(document_id, viewer=request.user)
        except ValidationError as error:
            detail = str(error)
            if detail == "You do not have permission to access this policy document.":
                status_code = 403
            else:
                status_code = 404 if detail == "Policy document was not found." else 400
            return JsonResponse({"detail": detail}, status=status_code)
        return JsonResponse({"document": document})

    if not has_portal_permission(request.user, PortalResource.POLICY_DOCUMENT, PortalAction.DELETE):
        return portal_api_forbidden_response("You do not have permission to delete policy documents.")

    try:
        deleted_document = delete_uploaded_policy(document_id)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)

    actor_username, actor_display_name = current_audit_actor(request)
    deleted_document_id = str(deleted_document.get("id") or "")
    deleted_document_title = str(deleted_document.get("title") or deleted_document_id)
    append_portal_audit_entry(
        action="delete_policy_document",
        entity_type="policy",
        entity_id=deleted_document_id,
        summary=f"Deleted policy {deleted_document_title}.",
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "policies",
            "policyId": deleted_document_id,
            "policyTitle": deleted_document_title,
        },
    )

    return JsonResponse({"deletedDocument": deleted_document})


@api_login_required
@require_http_methods(["PATCH", "PUT"])
def policy_document_approver(request: HttpRequest, document_id: str) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.POLICY_DOCUMENT, PortalAction.ASSIGN):
        return portal_api_forbidden_response("You do not have permission to assign policy approvers.")

    body, error_response = parse_json_body_or_400(request)
    if error_response is not None:
        return error_response

    if not isinstance(body, dict) or "approver" not in body:
        return JsonResponse({"detail": "Approver is required."}, status=400)

    try:
        updated_document = update_uploaded_policy_approver(document_id, body.get("approver"))
    except ValidationError as error:
        status_code = 404 if str(error) == "Uploaded policy was not found." else 400
        return JsonResponse({"detail": str(error)}, status=status_code)

    return JsonResponse({"document": updated_document})


@api_login_required
@require_http_methods(["POST"])
def policy_document_approval(request: HttpRequest, document_id: str) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.POLICY_DOCUMENT, PortalAction.APPROVE):
        return portal_api_forbidden_response("You do not have permission to approve policy documents.")
    username, display_name = current_audit_actor(request)

    try:
        updated_document, review_state = approve_uploaded_policy(
            document_id,
            actor_username=username,
            actor_display_name=display_name,
        )
    except ValidationError as error:
        detail = str(error)
        status_code = 404 if detail == "Uploaded policy was not found." else 400
        if detail == "Only the assigned approver can approve this policy.":
            status_code = 403
        return JsonResponse({"detail": detail}, status=status_code)

    return JsonResponse(
        {
            "document": updated_document,
            "reviewState": review_state_payload_for_viewer(review_state, viewer=request.user),
            "auditLog": audit_log_payload_for_viewer(viewer=request.user),
        }
    )


@api_login_required
@require_http_methods(["POST"])
def upload_mapping(request: HttpRequest) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.MAPPING, PortalAction.CHANGE):
        return portal_api_forbidden_response("You do not have permission to modify mappings.")
    file_obj = request.FILES.get("file")
    if file_obj is None:
        files = request.FILES.getlist("files")
        file_obj = files[0] if files else None

    if file_obj is None:
        return JsonResponse({"detail": "Select a mapping file to upload."}, status=400)

    try:
        validate_mapping_upload_file(file_obj)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    try:
        mapping_payload = replace_mapping_payload(file_obj)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    actor_username, actor_display_name = current_audit_actor(request)
    controls = mapping_payload.get("controls") if isinstance(mapping_payload.get("controls"), list) else []
    documents = mapping_payload.get("documents") if isinstance(mapping_payload.get("documents"), list) else []
    mapping_file_name = str(getattr(file_obj, "name", "") or "").strip()
    append_portal_audit_entry(
        action="import_mapping",
        entity_type="mapping",
        entity_id=mapping_file_name or "mapping-upload",
        summary=f"Imported mapping file {mapping_file_name or 'mapping file'}.",
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "policies",
            "importType": "mapping_upload",
            "fileName": mapping_file_name,
            "controlCount": len(controls),
            "documentCount": len(documents),
        },
    )

    return JsonResponse({"mapping": mapping_payload})


@api_login_required
@require_http_methods(["GET", "POST"])
def upload_vendors(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        if not has_portal_permission(request.user, PortalResource.VENDOR_RESPONSE, PortalAction.VIEW):
            return portal_api_forbidden_response("You do not have permission to view vendor responses.")
        return JsonResponse({"responses": list_vendor_responses(viewer=request.user)})

    if not has_portal_permission(request.user, PortalResource.VENDOR_RESPONSE, PortalAction.ADD):
        return portal_api_forbidden_response("You do not have permission to import vendor responses.")

    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"detail": "Select at least one vendor response file to import."}, status=400)

    try:
        validate_vendor_upload_files(files)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    responses = create_vendor_responses(files)
    actor_username, actor_display_name = current_audit_actor(request)
    imported_file_names = [str(getattr(file, "name", "") or "").strip() for file in files]
    imported_file_preview = named_item_preview(imported_file_names)
    append_portal_audit_entry(
        action="import_vendor_responses",
        entity_type="vendor_response",
        entity_id=f"{len(responses)}",
        summary=(
            f"Imported vendor response file{'s' if len(imported_file_names) != 1 else ''}: {imported_file_preview}."
            if imported_file_preview
            else f"Imported {len(responses)} vendor response file{'s' if len(responses) != 1 else ''}."
        ),
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "vendors",
            "importType": "vendor_response_upload",
            "responseCount": len(responses),
            "responseIds": [str(item.get("id") or "") for item in responses if isinstance(item, dict)],
            "fileNames": imported_file_names,
        },
    )
    return JsonResponse({"responses": responses})


@api_login_required
@require_http_methods(["DELETE"])
def vendor_response(request: HttpRequest, response_id: str) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.VENDOR_RESPONSE, PortalAction.DELETE):
        return portal_api_forbidden_response("You do not have permission to delete vendor responses.")
    try:
        deleted_response = delete_vendor_response(response_id)
    except ValidationError as error:
        detail = str(error)
        status_code = 404 if detail == "Vendor response was not found." else 400
        return JsonResponse({"detail": detail}, status=status_code)

    actor_username, actor_display_name = current_audit_actor(request)
    deleted_response_id = str(deleted_response.get("id") or "")
    vendor_name = str(deleted_response.get("vendorName") or "").strip()
    response_file_name = str(deleted_response.get("fileName") or "").strip()
    deleted_response_label = response_file_name or vendor_name or deleted_response_id
    append_portal_audit_entry(
        action="delete_vendor_response",
        entity_type="vendor_response",
        entity_id=deleted_response_id,
        summary=f"Deleted vendor response {deleted_response_label}.",
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "vendors",
            "vendorName": vendor_name,
            "fileName": response_file_name,
            "responseId": deleted_response_id,
        },
    )
    return JsonResponse({"deletedResponse": deleted_response})


@api_login_required
@require_http_methods(["GET", "POST", "PUT"])
def risk_register(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        if not has_portal_permission(request.user, PortalResource.RISK_RECORD, PortalAction.VIEW):
            return portal_api_forbidden_response("You do not have permission to view risk records.")
        return JsonResponse({"riskRegister": list_risk_register(viewer=request.user)})

    body, error_response = parse_json_body_or_400(request)
    if error_response is not None:
        return error_response

    if request.method == "POST":
        if not has_portal_permission(request.user, PortalResource.RISK_RECORD, PortalAction.ADD):
            return portal_api_forbidden_response("You do not have permission to create risk records.")
        if not isinstance(body, dict) or "risk" not in body:
            return JsonResponse({"detail": "Risk payload is required."}, status=400)
        payload = body.get("risk")
        try:
            created_risk = create_risk_record(payload, viewer=request.user)
        except ValidationError as error:
            return JsonResponse({"detail": str(error)}, status=400)
        return JsonResponse({"risk": created_risk}, status=201)

    if not has_portal_permission(request.user, PortalResource.RISK_RECORD, PortalAction.CHANGE):
        return portal_api_forbidden_response("You do not have permission to modify risk records.")

    if not isinstance(body, dict) or "riskRegister" not in body:
        return JsonResponse({"detail": "riskRegister payload is required."}, status=400)
    items = body.get("riskRegister")
    try:
        risk_register_payload = replace_risk_register(items, viewer=request.user)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    if isinstance(items, str):
        actor_username, actor_display_name = current_audit_actor(request)
        risk_name_preview = named_item_preview(
            [str(item.get("risk") or "").strip() for item in risk_register_payload if isinstance(item, dict)]
        )
        append_portal_audit_entry(
            action="import_risk_csv",
            entity_type="risk_register",
            entity_id=f"{len(risk_register_payload)}",
            summary=(
                f"Imported risk entries: {risk_name_preview}."
                if risk_name_preview
                else f"Imported risk CSV with {len(risk_register_payload)} risk record{'s' if len(risk_register_payload) != 1 else ''}."
            ),
            actor_username=actor_username,
            actor_display_name=actor_display_name,
            metadata={
                "source": "risks",
                "importType": "risk_csv",
                "recordCount": len(risk_register_payload),
            },
        )

    return JsonResponse({"riskRegister": risk_register_payload})


@api_login_required
@require_http_methods(["PATCH", "PUT", "DELETE"])
def risk_record(request: HttpRequest, risk_id: str) -> JsonResponse:
    if request.method == "DELETE":
        if not has_portal_permission(request.user, PortalResource.RISK_RECORD, PortalAction.DELETE):
            return portal_api_forbidden_response("You do not have permission to delete risk records.")
        try:
            deleted_risk = delete_risk_record(risk_id)
        except ValidationError as error:
            detail = str(error)
            status_code = 404 if detail == "Risk record was not found." else 400
            return JsonResponse({"detail": detail}, status=status_code)
        actor_username, actor_display_name = current_audit_actor(request)
        deleted_risk_id = str(deleted_risk.get("id") or "")
        deleted_risk_name = str(deleted_risk.get("risk") or "").strip()
        if not deleted_risk_name:
            deleted_risk_name = deleted_risk_id
        append_portal_audit_entry(
            action="delete_risk_record",
            entity_type="risk",
            entity_id=deleted_risk_id,
            summary=f"Deleted risk '{deleted_risk_name}'.",
            actor_username=actor_username,
            actor_display_name=actor_display_name,
            metadata={
                "source": "risks",
                "riskId": deleted_risk_id,
                "risk": str(deleted_risk.get("risk") or ""),
            },
        )
        return JsonResponse({"deletedRisk": deleted_risk})

    body, error_response = parse_json_body_or_400(request)
    if error_response is not None:
        return error_response

    if not isinstance(body, dict) or "risk" not in body:
        return JsonResponse({"detail": "Risk payload is required."}, status=400)
    if not has_portal_permission(request.user, PortalResource.RISK_RECORD, PortalAction.CHANGE):
        return portal_api_forbidden_response("You do not have permission to modify risk records.")
    payload = body.get("risk")
    try:
        updated_risk = update_risk_record(risk_id, payload, viewer=request.user)
    except ValidationError as error:
        detail = str(error)
        status_code = 404 if detail == "Risk record was not found." else 400
        return JsonResponse({"detail": detail}, status=status_code)
    return JsonResponse({"risk": updated_risk})


@api_login_required
@require_http_methods(["POST"])
def checklist_items(request: HttpRequest) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.REVIEW_STATE, PortalAction.CHANGE):
        return portal_api_forbidden_response("You do not have permission to modify review tasks.")
    body, error_response = parse_json_body_or_400(request)
    if error_response is not None:
        return error_response

    if not isinstance(body, dict) or "checklistItem" not in body:
        return JsonResponse({"detail": "Checklist item payload is required."}, status=400)
    payload = body.get("checklistItem")

    try:
        checklist_item = create_review_checklist_item(payload, viewer=request.user)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    return JsonResponse({"checklistItem": checklist_item}, status=201)


@api_login_required
@require_http_methods(["DELETE"])
def checklist_item(request: HttpRequest, checklist_item_id: str) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.REVIEW_STATE, PortalAction.DELETE):
        return portal_api_forbidden_response("You do not have permission to delete review tasks.")
    try:
        deleted_checklist_item = delete_review_checklist_item(checklist_item_id)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)

    actor_username, actor_display_name = current_audit_actor(request)
    deleted_item_id = str(deleted_checklist_item.get("id") or "")
    deleted_item_name = str(deleted_checklist_item.get("item") or "").strip()
    append_portal_audit_entry(
        action="delete_checklist_item",
        entity_type="checklist_item",
        entity_id=deleted_item_id,
        summary=(
            f"Deleted checklist item '{deleted_item_name}'."
            if deleted_item_name
            else f"Deleted checklist item {deleted_item_id}."
        ),
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "review-tasks",
            "checklistItemId": deleted_item_id,
            "item": str(deleted_checklist_item.get("item") or ""),
        },
    )

    return JsonResponse({"deletedChecklistItem": deleted_checklist_item})


@api_login_required
@require_http_methods(["PUT"])
def review_state(request: HttpRequest) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.REVIEW_STATE, PortalAction.CHANGE):
        return portal_api_forbidden_response("You do not have permission to modify review state.")
    body, error_response = parse_json_body_or_400(request)
    if error_response is not None:
        return error_response

    if not isinstance(body, dict) or "reviewState" not in body:
        return JsonResponse({"detail": "reviewState payload is required."}, status=400)
    payload = body.get("reviewState")
    username, display_name = current_audit_actor(request)
    normalized = update_review_state(
        payload,
        actor_username=username,
        actor_display_name=display_name,
    )
    return JsonResponse(
        {
            "reviewState": review_state_payload_for_viewer(normalized, viewer=request.user),
            "auditLog": audit_log_payload_for_viewer(viewer=request.user),
        }
    )


@api_login_required
@require_http_methods(["PUT"])
def control_state(request: HttpRequest) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.CONTROL_STATE, PortalAction.CHANGE):
        return portal_api_forbidden_response("You do not have permission to modify control state.")
    body, error_response = parse_json_body_or_400(request)
    if error_response is not None:
        return error_response

    if not isinstance(body, dict) or "controlState" not in body:
        return JsonResponse({"detail": "controlState payload is required."}, status=400)
    payload = body.get("controlState")
    normalized = normalize_control_state(payload, viewer=request.user)
    set_state_payload("control_state", normalized)
    return JsonResponse({"controlState": normalized})


@api_login_required
@require_http_methods(["PUT"])
def mapping_state(request: HttpRequest) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.MAPPING, PortalAction.CHANGE):
        return portal_api_forbidden_response("You do not have permission to modify mappings.")
    body, error_response = parse_json_body_or_400(request)
    if error_response is not None:
        return error_response

    if not isinstance(body, dict) or "mapping" not in body:
        return JsonResponse({"detail": "mapping payload is required."}, status=400)
    payload = body.get("mapping")
    normalized = normalize_mapping_payload(payload)
    set_state_payload("mapping_state", normalized)
    return JsonResponse({"mapping": normalized})
