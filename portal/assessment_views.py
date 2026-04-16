from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_http_methods

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
from .views import api_login_required, parse_json_body, render_portal_page


def assessment_staff_page_required(view_func):
    def wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponse("Forbidden", status=403)
        return view_func(request, *args, **kwargs)

    return wrapped


def assessment_staff_api_required(view_func):
    def wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_staff:
            return JsonResponse({"detail": "Only staff users can manage assessments."}, status=403)
        return view_func(request, *args, **kwargs)

    return api_login_required(wrapped)


@login_required(login_url="portal-login")
@assessment_staff_page_required
@ensure_csrf_cookie
def assessments_page(request: HttpRequest) -> HttpResponse:
    return render_portal_page(request, "portal/assessments.html")


@assessment_staff_api_required
@require_http_methods(["GET", "POST"])
def assessments_collection(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return JsonResponse({"profiles": list_zero_trust_profiles()})

    body = parse_json_body(request)
    payload = body.get("profile") if isinstance(body, dict) and "profile" in body else body
    try:
        profile = save_zero_trust_profile(payload)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)
    return JsonResponse({"profile": profile})


@assessment_staff_api_required
@require_http_methods(["GET", "DELETE"])
def assessment_profile_detail(request: HttpRequest, profile_id: str) -> JsonResponse:
    if request.method == "DELETE":
        try:
            deleted_profile = delete_zero_trust_profile(profile_id)
        except AssessmentValidationError as error:
            detail = str(error)
            status_code = 404 if detail == "Assessment profile was not found." else 400
            return JsonResponse({"detail": detail}, status=status_code)
        return JsonResponse({"deletedProfile": deleted_profile})

    try:
        detail = get_zero_trust_profile_detail(profile_id)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)
    return JsonResponse(detail)


@assessment_staff_api_required
@require_http_methods(["POST"])
def assessment_profile_certificate(request: HttpRequest, profile_id: str) -> JsonResponse:
    try:
        payload = generate_zero_trust_certificate(profile_id)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)
    return JsonResponse(payload, status=201)


@assessment_staff_api_required
@require_GET
def assessment_profile_certificate_download(request: HttpRequest, profile_id: str) -> HttpResponse:
    try:
        file_name, content = get_zero_trust_certificate_download(profile_id)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)

    response = HttpResponse(content, content_type="application/pkix-cert")
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@assessment_staff_api_required
@require_http_methods(["POST"])
def assessment_profile_runs(request: HttpRequest, profile_id: str) -> JsonResponse:
    actor_username = request.user.get_username() if request.user.is_authenticated else ""
    try:
        run = create_zero_trust_run(profile_id, actor_username=actor_username)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)
    return JsonResponse({"run": run}, status=201)


@assessment_staff_api_required
@require_GET
def assessment_run_detail(request: HttpRequest, run_id: str) -> JsonResponse:
    try:
        payload = get_zero_trust_run_detail(run_id)
    except AssessmentValidationError as error:
        return JsonResponse({"detail": str(error)}, status=404)
    return JsonResponse(payload)


@assessment_staff_api_required
@require_GET
def assessment_run_logs(request: HttpRequest, run_id: str) -> JsonResponse:
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
@assessment_staff_page_required
@xframe_options_sameorigin
@require_GET
def assessment_run_report(request: HttpRequest, run_id: str) -> HttpResponse:
    try:
        html = get_zero_trust_report_html(run_id)
    except AssessmentValidationError as error:
        return HttpResponse(str(error), status=404, content_type="text/plain; charset=utf-8")

    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Content-Security-Policy"] = (
        "default-src 'self' data: blob:; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval';"
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required(login_url="portal-login")
@assessment_staff_page_required
@require_GET
def assessment_run_artifact(request: HttpRequest, run_id: str, relative_path: str) -> HttpResponse:
    try:
        artifact = get_zero_trust_artifact(run_id, relative_path=relative_path)
    except AssessmentValidationError as error:
        return HttpResponse(str(error), status=404, content_type="text/plain; charset=utf-8")

    response = HttpResponse(bytes(artifact.content), content_type=artifact.content_type)
    response["X-Content-Type-Options"] = "nosniff"
    return response
