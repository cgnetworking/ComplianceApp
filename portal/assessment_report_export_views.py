from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .assessment_services import AssessmentValidationError
from .assessment_views import assessment_staff_api_required
from .services.assessment_report_exports import (
    create_assessment_reports_export,
    create_assessment_run_report_export,
)

ASSESSMENT_EXPORT_NOT_FOUND_ERRORS = frozenset(
    {
        "Assessment profile was not found.",
        "Assessment run was not found.",
        "This assessment run does not have a stored report.",
        "Stored assessment report artifacts were not found.",
        "No stored assessment reports are available for export.",
    }
)


def assessment_export_response(file_name: str, content: bytes) -> HttpResponse:
    response = HttpResponse(content, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


def assessment_export_error_response(error: AssessmentValidationError) -> JsonResponse:
    detail = str(error)
    status_code = 404 if detail in ASSESSMENT_EXPORT_NOT_FOUND_ERRORS else 400
    return JsonResponse({"detail": detail}, status=status_code)


@assessment_staff_api_required
@require_GET
def assessment_run_report_export(request: HttpRequest, run_id: str) -> HttpResponse:
    try:
        file_name, content = create_assessment_run_report_export(run_id)
    except AssessmentValidationError as error:
        return assessment_export_error_response(error)
    return assessment_export_response(file_name, content)


@assessment_staff_api_required
@require_GET
def assessment_reports_export(request: HttpRequest) -> HttpResponse:
    profile_id = str(request.GET.get("profileId") or "").strip()
    try:
        file_name, content = create_assessment_reports_export(profile_id=profile_id)
    except AssessmentValidationError as error:
        return assessment_export_error_response(error)
    return assessment_export_response(file_name, content)
