from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_http_methods

from .authorization import (
    PAGE_PERMISSION_REQUIREMENTS,
    PortalAction,
    PortalResource,
    has_portal_permission,
)
from .services.bootstrap import append_portal_audit_entry
from .assessment_services import (
    AssessmentValidationError,
    create_zero_trust_run,
    delete_zero_trust_profile,
    generate_zero_trust_certificate,
    get_zero_trust_artifact,
    get_zero_trust_certificate_download,
    get_zero_trust_profile_detail,
    get_zero_trust_report_html,
    get_zero_trust_run_detail,
    list_zero_trust_profiles,
    list_zero_trust_run_logs,
    save_zero_trust_profile,
)
from .view_helpers import (
    api_login_required,
    current_audit_actor,
    parse_json_body_or_400,
    portal_api_forbidden_response,
    portal_page_permission_required,
    render_portal_page,
)


ASSESSMENT_PERMISSION_DETAIL = "You do not have permission to access assessments."


ASSESSMENT_REPORT_CSP = (
    "default-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'; "
    "form-action 'none'; "
    "connect-src 'none'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "media-src 'self'; "
    "style-src 'self'; "
    "script-src 'none'; "
    "object-src 'none'; "
    "sandbox;"
)


def apply_assessment_report_security_headers(response: HttpResponse) -> None:
    response["Content-Security-Policy"] = ASSESSMENT_REPORT_CSP
    response["Cross-Origin-Opener-Policy"] = "same-origin"
    response["Permissions-Policy"] = (
        "accelerometer=(), autoplay=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    )
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"


def assessment_audit_actor(request: HttpRequest) -> tuple[str, str]:
    return current_audit_actor(
        request,
        error_cls=AssessmentValidationError,
        message="Authenticated assessment actions require a username.",
    )


@login_required(login_url="portal-login")
@ensure_csrf_cookie
@portal_page_permission_required(*PAGE_PERMISSION_REQUIREMENTS["assessments"])
def assessments_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/assessments.html")


@api_login_required
@require_http_methods(["GET", "POST"])
def assessments_collection(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.VIEW):
            return portal_api_forbidden_response(ASSESSMENT_PERMISSION_DETAIL)
        return JsonResponse({"profiles": list_zero_trust_profiles()})

    if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.CHANGE):
        return portal_api_forbidden_response(ASSESSMENT_PERMISSION_DETAIL)

    body, error_response = parse_json_body_or_400(request)
    if error_response is not None:
        return error_response

    if not isinstance(body, dict) or "profile" not in body:
        return JsonResponse({"detail": "Profile payload is required."}, status=400)
    payload = body.get("profile")
    try:
        profile = save_zero_trust_profile(payload)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)
    return JsonResponse({"profile": profile})


@api_login_required
@require_http_methods(["GET", "DELETE"])
def assessment_profile_detail(request: HttpRequest, profile_id: str) -> JsonResponse:
    if request.method == "DELETE":
        if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.DELETE):
            return portal_api_forbidden_response(ASSESSMENT_PERMISSION_DETAIL)
        try:
            deleted_profile = delete_zero_trust_profile(profile_id)
        except AssessmentValidationError as error:
            detail = str(error)
            status_code = 404 if detail == "Assessment profile was not found." else 400
            return JsonResponse({"detail": detail}, status=status_code)

        actor_username, actor_display_name = assessment_audit_actor(request)
        deleted_profile_id = str(deleted_profile.get("id") or "")
        append_portal_audit_entry(
            action="delete_assessment_profile",
            entity_type="assessment_profile",
            entity_id=deleted_profile_id,
            summary=f"Deleted assessment profile {deleted_profile_id}.",
            actor_username=actor_username,
            actor_display_name=actor_display_name,
            metadata={
                "source": "assessments",
                "profileId": deleted_profile_id,
                "tenantId": str(deleted_profile.get("tenantId") or ""),
                "displayName": str(deleted_profile.get("displayName") or ""),
            },
        )
        return JsonResponse({"deletedProfile": deleted_profile})

    if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.VIEW):
        return portal_api_forbidden_response(ASSESSMENT_PERMISSION_DETAIL)
    try:
        detail = get_zero_trust_profile_detail(profile_id)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)
    return JsonResponse(detail)


@api_login_required
@require_http_methods(["POST"])
def assessment_profile_certificate(request: HttpRequest, profile_id: str) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.CHANGE):
        return portal_api_forbidden_response(ASSESSMENT_PERMISSION_DETAIL)
    try:
        payload = generate_zero_trust_certificate(profile_id)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)
    return JsonResponse(payload, status=201)


@api_login_required
@require_GET
def assessment_profile_certificate_download(request: HttpRequest, profile_id: str) -> HttpResponse:
    if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.EXPORT):
        return portal_api_forbidden_response(ASSESSMENT_PERMISSION_DETAIL)
    try:
        file_name, content = get_zero_trust_certificate_download(profile_id)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)

    response = HttpResponse(content, content_type="application/pkix-cert")
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    response["X-Content-Type-Options"] = "nosniff"

    actor_username, actor_display_name = assessment_audit_actor(request)
    append_portal_audit_entry(
        action="export_assessment_certificate",
        entity_type="assessment_profile",
        entity_id=profile_id,
        summary=f"Exported assessment certificate file {file_name}.",
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "assessments",
            "exportType": "assessment_certificate",
            "profileId": profile_id,
            "fileName": file_name,
        },
    )
    return response


@api_login_required
@require_http_methods(["POST"])
def assessment_profile_runs(request: HttpRequest, profile_id: str) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.CHANGE):
        return portal_api_forbidden_response(ASSESSMENT_PERMISSION_DETAIL)
    actor_username = request.user.get_username().strip() if request.user.is_authenticated else ""
    try:
        run = create_zero_trust_run(profile_id, actor_username=actor_username)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)
    return JsonResponse({"run": run}, status=201)


@api_login_required
@require_GET
def assessment_run_detail(request: HttpRequest, run_id: str) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.VIEW):
        return portal_api_forbidden_response(ASSESSMENT_PERMISSION_DETAIL)
    try:
        payload = get_zero_trust_run_detail(run_id)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)
    return JsonResponse(payload)


@api_login_required
@require_GET
def assessment_run_logs(request: HttpRequest, run_id: str) -> JsonResponse:
    if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.VIEW):
        return portal_api_forbidden_response(ASSESSMENT_PERMISSION_DETAIL)
    after_value = request.GET.get("after", "0")
    try:
        after_sequence = max(0, int(after_value))
    except ValueError:
        after_sequence = 0

    try:
        logs = list_zero_trust_run_logs(run_id, after_sequence=after_sequence)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)
    return JsonResponse({"logs": logs})


@login_required(login_url="portal-login")
@xframe_options_sameorigin
@require_GET
def assessment_run_report(request: HttpRequest, run_id: str) -> HttpResponse:
    if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.VIEW):
        return HttpResponse("Forbidden", status=403)
    try:
        html = get_zero_trust_report_html(run_id)
    except AssessmentValidationError as error:
        return HttpResponse(str(error), status=404, content_type="text/plain; charset=utf-8")

    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    apply_assessment_report_security_headers(response)
    return response


@login_required(login_url="portal-login")
@require_GET
def assessment_run_artifact(request: HttpRequest, run_id: str, relative_path: str) -> HttpResponse:
    if not has_portal_permission(request.user, PortalResource.ASSESSMENT, PortalAction.VIEW):
        return HttpResponse("Forbidden", status=403)
    try:
        artifact = get_zero_trust_artifact(run_id, relative_path=relative_path)
    except AssessmentValidationError as error:
        return HttpResponse(str(error), status=404, content_type="text/plain; charset=utf-8")

    response = HttpResponse(bytes(artifact.content), content_type=artifact.content_type)
    if artifact.content_type.lower().startswith("text/html"):
        apply_assessment_report_security_headers(response)
    else:
        response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response
