from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

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


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_GET
def vendor_response_downloads(request: HttpRequest) -> HttpResponse:
    scope = normalize_string(request.GET.get("scope")).lower()
    response_id = request.GET.get("responseId") or request.GET.get("id")

    try:
        if scope == "all":
            file_name, content, content_type = build_all_vendor_responses_download()
        else:
            file_name, content, content_type = build_single_vendor_response_download(response_id)
    except ValidationError as error:
        return vendor_download_error_response(error)

    return build_vendor_download_response(file_name, content, content_type)


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_GET
def vendor_response_download(request: HttpRequest, response_id: str) -> HttpResponse:
    try:
        file_name, content, content_type = build_single_vendor_response_download(response_id)
    except ValidationError as error:
        return vendor_download_error_response(error)

    return build_vendor_download_response(file_name, content, content_type)


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_GET
def vendor_response_download_all(request: HttpRequest) -> HttpResponse:
    file_name, content, content_type = build_all_vendor_responses_download()
    return build_vendor_download_response(file_name, content, content_type)


__all__ = [
    "vendor_response_download",
    "vendor_response_download_all",
    "vendor_response_downloads",
]
