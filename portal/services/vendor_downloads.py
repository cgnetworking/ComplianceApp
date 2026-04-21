from __future__ import annotations

import csv
import io
import json
import re
from urllib.parse import quote

from django.utils import timezone

from ..authorization import PortalAction, PortalResource, has_portal_permission, restrict_queryset
from ..contracts import serialize_vendor_response
from ..models import VendorResponse
from .common import ValidationError, normalize_string

SAFE_FILENAME_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")
SAFE_EXTENSION_RE = re.compile(r"^[a-z0-9]{1,16}$")
MIME_TYPE_BY_EXTENSION = {
    "csv": "text/csv; charset=utf-8",
    "html": "text/html; charset=utf-8",
    "htm": "text/html; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
    "xml": "application/xml; charset=utf-8",
}
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_filename_component(value: object) -> str:
    normalized = normalize_string(value)
    safe_value = SAFE_FILENAME_CHARS_RE.sub("-", normalized).strip("-._")
    safe_value = re.sub(r"-{2,}", "-", safe_value)
    if safe_value:
        return safe_value
    raise ValidationError("Vendor download file name component is required.")


def normalize_download_extension(value: object) -> str:
    normalized = normalize_string(value).lower().lstrip(".")
    if SAFE_EXTENSION_RE.fullmatch(normalized or ""):
        return normalized
    raise ValidationError("Vendor download file extension is invalid.")


def build_attachment_disposition(file_name: str) -> str:
    safe_name = sanitize_filename_component(file_name)
    if "." not in safe_name:
        raise ValidationError("Vendor download file name must include an extension.")
    return f'attachment; filename="{safe_name}"; filename*=UTF-8\'\'{quote(file_name, safe="")}'


def get_vendor_response_for_download(response_id: object) -> VendorResponse:
    normalized_id = normalize_string(response_id)
    if not normalized_id:
        raise ValidationError("Vendor response id is required.")

    try:
        return VendorResponse.objects.get(external_id=normalized_id)
    except VendorResponse.DoesNotExist as error:
        raise ValidationError("Vendor response was not found.") from error


def build_vendor_response_file_name(response: VendorResponse, *, extension: str | None = None) -> str:
    vendor_component = sanitize_filename_component(response.vendor_name)
    timestamp_component = response.imported_at.strftime("%Y%m%d-%H%M%S")
    response_component = sanitize_filename_component(response.external_id)
    output_extension = normalize_download_extension(extension or response.extension)
    return f"{vendor_component}-{timestamp_component}-{response_component}.{output_extension}"


def normalize_download_mime_type(raw_mime_type: object, extension: str) -> str:
    normalized_mime_type = normalize_string(raw_mime_type).lower()
    if normalized_mime_type and normalized_mime_type != "unknown":
        if normalized_mime_type.startswith("text/") and "charset=" not in normalized_mime_type:
            return f"{normalized_mime_type}; charset=utf-8"
        return normalized_mime_type
    return MIME_TYPE_BY_EXTENSION.get(extension, "text/plain; charset=utf-8")


def escape_csv_formula(value: object) -> str:
    normalized = "" if value is None else str(value)
    if normalized.startswith(CSV_FORMULA_PREFIXES):
        return f"'{normalized}"
    return normalized


def build_vendor_response_metadata_download(response: VendorResponse) -> tuple[str, bytes, str]:
    file_name = build_vendor_response_file_name(response, extension="json")
    payload = serialize_vendor_response(response)
    payload["rawTextAvailable"] = bool((response.raw_text or "").replace("\x00", "").strip())
    content = json.dumps(payload, sort_keys=True).encode("utf-8")
    return file_name, content, MIME_TYPE_BY_EXTENSION["json"]


def build_single_vendor_response_download(
    response_id: object,
    *,
    viewer: object | None = None,
    include_raw_text: bool = False,
) -> tuple[str, bytes, str]:
    response = get_vendor_response_for_download(response_id)
    if viewer is not None and not has_portal_permission(viewer, PortalResource.VENDOR_RESPONSE, PortalAction.EXPORT):
        raise ValidationError("You do not have permission to export vendor responses.")

    raw_text = (response.raw_text or "").replace("\x00", "")

    if not include_raw_text or not raw_text:
        return build_vendor_response_metadata_download(response)

    extension = normalize_download_extension(response.extension)
    file_name = build_vendor_response_file_name(response, extension=extension)
    mime_type = normalize_download_mime_type(response.mime_type, extension)
    return file_name, raw_text.encode("utf-8"), mime_type


def build_all_vendor_responses_download(
    *,
    viewer: object | None = None,
    include_raw_text: bool = False,
) -> tuple[str, bytes, str]:
    if viewer is not None and not has_portal_permission(viewer, PortalResource.VENDOR_RESPONSE, PortalAction.EXPORT):
        raise ValidationError("You do not have permission to export vendor responses.")

    rows = restrict_queryset(
        VendorResponse.objects.all(),
        viewer,
        PortalAction.EXPORT,
        resource=PortalResource.VENDOR_RESPONSE,
    )
    timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"vendor-survey-responses-{timestamp}.csv"

    output = io.StringIO()
    field_names = [
        "id",
        "vendorName",
        "fileName",
        "extension",
        "mimeType",
        "fileSize",
        "importedAt",
        "summary",
        "status",
    ]
    if include_raw_text:
        field_names.append("rawText")
    writer = csv.DictWriter(output, fieldnames=field_names)
    writer.writeheader()

    for item in rows:
        row = {
            "id": escape_csv_formula(item.external_id),
            "vendorName": escape_csv_formula(item.vendor_name),
            "fileName": escape_csv_formula(item.file_name),
            "extension": escape_csv_formula(item.extension),
            "mimeType": escape_csv_formula(item.mime_type),
            "fileSize": escape_csv_formula(int(item.file_size or 0)),
            "importedAt": escape_csv_formula(item.imported_at.isoformat()),
            "summary": escape_csv_formula(item.summary),
            "status": escape_csv_formula(item.status),
        }
        if include_raw_text:
            row["rawText"] = escape_csv_formula(item.raw_text or "")
        writer.writerow(row)

    return file_name, output.getvalue().encode("utf-8"), MIME_TYPE_BY_EXTENSION["csv"]


__all__ = [
    "build_all_vendor_responses_download",
    "build_attachment_disposition",
    "build_single_vendor_response_download",
]
