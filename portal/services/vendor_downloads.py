from __future__ import annotations

import csv
import io
import json
import re
from urllib.parse import quote

from django.utils import timezone

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


def sanitize_filename_component(value: object, fallback: str) -> str:
    normalized = normalize_string(value)
    safe_value = SAFE_FILENAME_CHARS_RE.sub("-", normalized).strip("-._")
    safe_value = re.sub(r"-{2,}", "-", safe_value)
    if safe_value:
        return safe_value
    return fallback


def normalize_download_extension(value: object, fallback: str = "txt") -> str:
    normalized = normalize_string(value).lower().lstrip(".")
    if SAFE_EXTENSION_RE.fullmatch(normalized or ""):
        return normalized

    normalized_fallback = normalize_string(fallback).lower().lstrip(".")
    return normalized_fallback if SAFE_EXTENSION_RE.fullmatch(normalized_fallback or "") else "txt"


def build_attachment_disposition(file_name: str) -> str:
    safe_name = sanitize_filename_component(file_name, "vendor-response.txt")
    if "." not in safe_name:
        safe_name = f"{safe_name}.txt"
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
    vendor_component = sanitize_filename_component(response.vendor_name, "vendor")
    timestamp_component = response.imported_at.strftime("%Y%m%d-%H%M%S")
    response_component = sanitize_filename_component(response.external_id, "response")
    output_extension = normalize_download_extension(extension or response.extension or "txt")
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


def build_single_vendor_response_download(response_id: object) -> tuple[str, bytes, str]:
    response = get_vendor_response_for_download(response_id)
    raw_text = (response.raw_text or "").replace("\x00", "")

    if raw_text:
        extension = normalize_download_extension(response.extension or "txt")
        file_name = build_vendor_response_file_name(response, extension=extension)
        mime_type = normalize_download_mime_type(response.mime_type, extension)
        return file_name, raw_text.encode("utf-8"), mime_type

    metadata_file_name = build_vendor_response_file_name(response, extension="json")
    payload = {
        "id": response.external_id,
        "vendorName": response.vendor_name,
        "fileName": response.file_name,
        "extension": response.extension,
        "mimeType": response.mime_type,
        "fileSize": int(response.file_size or 0),
        "importedAt": response.imported_at.isoformat(),
        "summary": response.summary,
        "status": response.status,
        "rawTextAvailable": False,
    }
    return metadata_file_name, json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8"), MIME_TYPE_BY_EXTENSION["json"]


def build_all_vendor_responses_download() -> tuple[str, bytes, str]:
    rows = VendorResponse.objects.all()
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
        "rawText",
    ]
    writer = csv.DictWriter(output, fieldnames=field_names)
    writer.writeheader()

    for item in rows:
        writer.writerow(
            {
                "id": escape_csv_formula(item.external_id),
                "vendorName": escape_csv_formula(item.vendor_name),
                "fileName": escape_csv_formula(item.file_name),
                "extension": escape_csv_formula(item.extension),
                "mimeType": escape_csv_formula(item.mime_type),
                "fileSize": escape_csv_formula(int(item.file_size or 0)),
                "importedAt": escape_csv_formula(item.imported_at.isoformat()),
                "summary": escape_csv_formula(item.summary),
                "status": escape_csv_formula(item.status),
                "rawText": escape_csv_formula(item.raw_text or ""),
            }
        )

    return file_name, output.getvalue().encode("utf-8"), MIME_TYPE_BY_EXTENSION["csv"]


__all__ = [
    "build_all_vendor_responses_download",
    "build_attachment_disposition",
    "build_single_vendor_response_download",
]
