from __future__ import annotations

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from .common import (
    ValidationError,
    default_mapping_payload,
    get_state_payload,
    normalize_mapping_payload,
    parse_mapping_text,
    set_state_payload,
)
from .uploads import SUPPORTED_MAPPING_EXTENSIONS, decode_upload


def replace_mapping_payload(file: UploadedFile) -> dict[str, object]:
    extension = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
    if extension not in SUPPORTED_MAPPING_EXTENSIONS:
        raise ValidationError("Upload a JSON or CSV mapping file (.json, .csv).")

    parsed_payload = parse_mapping_text(
        decode_upload(file, max_bytes=int(settings.MAPPING_UPLOAD_MAX_FILE_BYTES)),
        extension,
    )
    normalized_payload = normalize_mapping_payload(parsed_payload)
    set_state_payload("mapping_state", normalized_payload)
    return normalized_payload


def get_mapping_payload() -> dict[str, object]:
    payload = get_state_payload("mapping_state", {})
    return normalize_mapping_payload(payload)


__all__ = ["get_mapping_payload", "replace_mapping_payload", "ValidationError", "default_mapping_payload", "normalize_mapping_payload"]
