from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .services.bootstrap import append_portal_audit_entry
from .services.common import ValidationError, normalize_string
from .services.vendor_downloads import (
    build_all_vendor_responses_download,
    build_attachment_disposition,
    build_single_vendor_response_download,
)
from .views import api_login_required, policy_reader_api_access


def vendor_download_error_response(error: ValidationError) -> JsonResponse:
    detail = str(error)
    status_code = 404 if detail == "Vendor response was not found." else 400
    return JsonResponse({"detail": detail}, status=status_code)


def build_vendor_download_response(file_name: str, content: bytes, content_type: str) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = build_attachment_disposition(file_name)
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def vendor_download_actor(request: HttpRequest) -> tuple[str, str]:
    username = request.user.get_username() if request.user.is_authenticated else ""
    display_name = request.user.get_full_name().strip() if request.user.is_authenticated else ""
    normalized_username = username or "system"
    normalized_display_name = display_name or username or "System"
    return normalized_username, normalized_display_name


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_GET
def vendor_response_downloads(request: HttpRequest) -> HttpResponse:
    scope = normalize_string(request.GET.get("scope")).lower()
    response_id = request.GET.get("responseId") or request.GET.get("id")

    try:
        if scope == "all":
            file_name, content, content_type = build_all_vendor_responses_download()
            action = "export_vendor_responses"
            entity_id = "all"
            summary = "Exported all vendor responses."
            metadata = {
                "source": "vendors",
                "exportType": "all_vendor_responses",
                "scope": "all",
                "fileName": file_name,
            }
        else:
            file_name, content, content_type = build_single_vendor_response_download(response_id)
            normalized_response_id = normalize_string(response_id)
            action = "export_vendor_response"
            entity_id = normalized_response_id
            summary = f"Exported vendor response {normalized_response_id or file_name}."
            metadata = {
                "source": "vendors",
                "exportType": "single_vendor_response",
                "scope": "single",
                "responseId": normalized_response_id,
                "fileName": file_name,
            }
    except ValidationError as error:
        return vendor_download_error_response(error)

    actor_username, actor_display_name = vendor_download_actor(request)
    append_portal_audit_entry(
        action=action,
        entity_type="vendor_response",
        entity_id=entity_id,
        summary=summary,
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata=metadata,
    )
    return build_vendor_download_response(file_name, content, content_type)


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_GET
def vendor_response_download(request: HttpRequest, response_id: str) -> HttpResponse:
    try:
        file_name, content, content_type = build_single_vendor_response_download(response_id)
    except ValidationError as error:
        return vendor_download_error_response(error)

    normalized_response_id = normalize_string(response_id)
    actor_username, actor_display_name = vendor_download_actor(request)
    append_portal_audit_entry(
        action="export_vendor_response",
        entity_type="vendor_response",
        entity_id=normalized_response_id,
        summary=f"Exported vendor response {normalized_response_id or file_name}.",
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "vendors",
            "exportType": "single_vendor_response",
            "scope": "single",
            "responseId": normalized_response_id,
            "fileName": file_name,
        },
    )
    return build_vendor_download_response(file_name, content, content_type)


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_GET
def vendor_response_download_all(request: HttpRequest) -> HttpResponse:
    file_name, content, content_type = build_all_vendor_responses_download()

    actor_username, actor_display_name = vendor_download_actor(request)
    append_portal_audit_entry(
        action="export_vendor_responses",
        entity_type="vendor_response",
        entity_id="all",
        summary="Exported all vendor responses.",
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "vendors",
            "exportType": "all_vendor_responses",
            "scope": "all",
            "fileName": file_name,
        },
    )
    return build_vendor_download_response(file_name, content, content_type)


__all__ = [
    "vendor_response_download",
    "vendor_response_download_all",
    "vendor_response_downloads",
]
