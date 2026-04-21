from __future__ import annotations

import csv
import html
import io
import json
import re

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from .common import ValidationError, normalize_string
from .html_sanitization import extract_purpose_from_markdown, sanitize_uploaded_html

SUPPORTED_POLICY_EXTENSIONS = {"md", "markdown", "txt", "html", "htm"}
SUPPORTED_MAPPING_EXTENSIONS = {"json", "csv"}
TEXT_VENDOR_EXTENSIONS = {"csv", "json", "txt", "md", "markdown", "html", "htm", "xml"}
BINARY_VENDOR_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx"}
SUPPORTED_VENDOR_EXTENSIONS = TEXT_VENDOR_EXTENSIONS | BINARY_VENDOR_EXTENSIONS
DANGEROUS_UPLOAD_MIME_TYPES = frozenset(
    {
        "application/x-dosexec",
        "application/x-executable",
        "application/x-msdos-program",
        "application/x-msdownload",
        "application/x-sh",
        "application/x-shellscript",
        "application/x-bat",
    }
)


def format_uploaded_policy_id(number: int) -> str:
    return f"UPL-{number:02d}"


def file_extension(file_name: str) -> str:
    parts = str(file_name).lower().split(".")
    return parts[-1] if len(parts) > 1 else ""


def file_name_base(file_name: str) -> str:
    without_extension = re.sub(r"\.[^.]+$", "", str(file_name))
    normalized = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", without_extension)).strip()
    return normalized or str(file_name)


def upload_size_label(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} byte(s)"


def normalized_upload_content_type(uploaded_file: UploadedFile) -> str:
    return normalize_string(uploaded_file.content_type).split(";", 1)[0].strip().lower()


def read_upload_bytes(uploaded_file: UploadedFile, *, max_bytes: int | None = None) -> bytes:
    if max_bytes is not None and max_bytes > 0 and int(uploaded_file.size or 0) > max_bytes:
        raise ValidationError(
            f"{uploaded_file.name} exceeds the {upload_size_label(max_bytes)} upload limit."
        )

    chunks: list[bytes] = []
    bytes_read = 0
    uploaded_file.seek(0)
    try:
        for chunk in uploaded_file.chunks():
            chunk_bytes = chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8")
            bytes_read += len(chunk_bytes)
            if max_bytes is not None and max_bytes > 0 and bytes_read > max_bytes:
                raise ValidationError(
                    f"{uploaded_file.name} exceeds the {upload_size_label(max_bytes)} upload limit."
                )
            chunks.append(chunk_bytes)
    finally:
        uploaded_file.seek(0)

    return b"".join(chunks)


def validate_uploaded_file_type_and_eicar_signature(
    uploaded_file: UploadedFile,
    *,
    max_bytes: int,
    expect_text: bool,
) -> None:
    content_type = normalized_upload_content_type(uploaded_file)
    if content_type in DANGEROUS_UPLOAD_MIME_TYPES:
        raise ValidationError(f"{uploaded_file.name} uses a blocked upload type.")

    payload = read_upload_bytes(uploaded_file, max_bytes=max_bytes)
    if expect_text and b"\x00" in payload:
        raise ValidationError(f"{uploaded_file.name} appears to be binary data, but a text file was expected.")


def validate_policy_upload_files(files: list[UploadedFile]) -> None:
    max_files = int(settings.POLICY_UPLOAD_MAX_FILES)
    if len(files) > max_files:
        raise ValidationError(f"Upload up to {max_files} policy file(s) at a time.")

    max_bytes = int(settings.POLICY_UPLOAD_MAX_FILE_BYTES)
    for uploaded_file in files:
        extension = file_extension(uploaded_file.name)
        if extension not in SUPPORTED_POLICY_EXTENSIONS:
            continue
        validate_uploaded_file_type_and_eicar_signature(
            uploaded_file,
            max_bytes=max_bytes,
            expect_text=True,
        )


def validate_mapping_upload_file(uploaded_file: UploadedFile) -> None:
    extension = file_extension(uploaded_file.name)
    if extension not in SUPPORTED_MAPPING_EXTENSIONS:
        raise ValidationError("Upload a JSON or CSV mapping file (.json, .csv).")
    validate_uploaded_file_type_and_eicar_signature(
        uploaded_file,
        max_bytes=int(settings.MAPPING_UPLOAD_MAX_FILE_BYTES),
        expect_text=True,
    )


def validate_vendor_upload_files(files: list[UploadedFile]) -> None:
    max_files = int(settings.VENDOR_UPLOAD_MAX_FILES)
    if len(files) > max_files:
        raise ValidationError(f"Upload up to {max_files} vendor response file(s) at a time.")

    max_bytes = int(settings.VENDOR_UPLOAD_MAX_FILE_BYTES)
    allowed_extensions = ", ".join(sorted(SUPPORTED_VENDOR_EXTENSIONS))
    for uploaded_file in files:
        extension = file_extension(uploaded_file.name)
        if extension not in SUPPORTED_VENDOR_EXTENSIONS:
            raise ValidationError(
                f"{uploaded_file.name} is not a supported vendor upload type. Allowed extensions: {allowed_extensions}."
            )
        validate_uploaded_file_type_and_eicar_signature(
            uploaded_file,
            max_bytes=max_bytes,
            expect_text=extension in TEXT_VENDOR_EXTENSIONS,
        )


def decode_upload(uploaded_file: UploadedFile, *, max_bytes: int | None = None) -> str:
    payload = read_upload_bytes(uploaded_file, max_bytes=max_bytes)
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{uploaded_file.name} must be valid UTF-8 text.") from error


def inline_markup(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


def table_cells(value: str) -> list[str]:
    trimmed = value.strip().strip("|")
    return [cell.strip() for cell in trimmed.split("|")]


def is_table_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def markdown_to_html(value: str) -> str:
    html_parts: list[str] = []
    lines = value.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            html_parts.append(f"<h{level}>{inline_markup(heading_match.group(2).strip())}</h{level}>")
            index += 1
            continue

        if stripped.startswith("- "):
            items: list[str] = []
            while index < len(lines):
                item_line = lines[index].strip()
                if not item_line.startswith("- "):
                    break
                items.append(f"<li>{inline_markup(item_line[2:].strip())}</li>")
                index += 1
            html_parts.append("<ul>" + "".join(items) + "</ul>")
            continue

        if stripped.startswith("|"):
            rows: list[list[str]] = []
            while index < len(lines):
                row_line = lines[index].strip()
                if not row_line.startswith("|"):
                    break
                rows.append(table_cells(row_line))
                index += 1
            if len(rows) >= 2 and is_table_separator(rows[1]):
                header = rows[0]
                body_rows = rows[2:]
                header_html = "".join(f"<th>{inline_markup(cell)}</th>" for cell in header)
                body_html = "".join(
                    "<tr>" + "".join(f"<td>{inline_markup(cell)}</td>" for cell in row) + "</tr>"
                    for row in body_rows
                )
                html_parts.append(
                    "<table><thead><tr>"
                    + header_html
                    + "</tr></thead><tbody>"
                    + body_html
                    + "</tbody></table>"
                )
            else:
                html_parts.extend(f"<p>{inline_markup(' | '.join(row))}</p>" for row in rows)
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            next_stripped = lines[index].strip()
            if not next_stripped or next_stripped.startswith("#") or next_stripped.startswith("- ") or next_stripped.startswith("|"):
                break
            paragraph_lines.append(next_stripped)
            index += 1
        html_parts.append(f"<p>{inline_markup(' '.join(paragraph_lines))}</p>")

    return "\n".join(html_parts)


def build_preview_text(raw_text: str, max_characters: int, max_lines: int) -> str:
    if not raw_text:
        return ""
    normalized = raw_text.replace("\r\n", "\n").strip()
    if not normalized:
        return ""

    lines = normalized.split("\n")
    limited_lines = lines[:max_lines]
    preview = "\n".join(limited_lines)
    truncated = len(limited_lines) < len(lines)

    if len(preview) > max_characters:
        preview = f"{preview[:max_characters].rstrip()}\n..."
        truncated = True
    elif truncated:
        preview = f"{preview}\n..."

    return preview


def is_text_like_file(uploaded_file: UploadedFile, extension: str) -> bool:
    if extension in TEXT_VENDOR_EXTENSIONS:
        return True
    content_type = (uploaded_file.content_type or "").lower()
    return content_type.startswith("text/") or "json" in content_type or "xml" in content_type


def summarize_vendor_survey(file_name: str, raw_text: str, extension: str, preview_text: str) -> str:
    non_empty_lines = len([line for line in raw_text.splitlines() if line.strip()]) if raw_text else 0
    if extension == "csv":
        row_count = max(non_empty_lines - 1, 0)
        return f"{row_count} questionnaire row(s) staged from CSV." if row_count else "CSV questionnaire staged for review."
    if extension == "json":
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return "JSON response staged with inline preview."
        if isinstance(parsed, list):
            return f"{len(parsed)} JSON record(s) staged for vendor review."
        if isinstance(parsed, dict):
            return f"{len(parsed.keys())} JSON field(s) staged for vendor review."
    if preview_text:
        return (
            f"{non_empty_lines} non-empty line(s) detected; preview trimmed for inline review."
            if non_empty_lines
            else "Text response staged with inline preview."
        )
    if extension in {"xls", "xlsx"}:
        return "Spreadsheet response staged with metadata only."
    if extension == "pdf":
        return "PDF response staged with metadata only."
    if extension in {"doc", "docx"}:
        return "Word document response staged with metadata only."
    return f"{file_name} staged with metadata only."


def infer_vendor_name(file_name: str, raw_text: str, extension: str) -> str:
    json_name = find_vendor_name_in_json(raw_text) if extension == "json" else ""
    if json_name:
        return json_name

    csv_name = find_vendor_name_in_csv(raw_text) if extension == "csv" else ""
    if csv_name:
        return csv_name

    base_name = re.sub(r"\.[^.]+$", "", file_name)
    cleaned = re.sub(
        r"\b(ddq|due diligence|questionnaire|security|survey|response|responses|sig lite|sig|caiq)\b",
        " ",
        base_name,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b20\d{2}[-_ ]?\d{2}[-_ ]?\d{2}\b", " ", cleaned)
    cleaned = re.sub(r"\b\d{8}\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", cleaned)).strip()
    return cleaned


def find_vendor_name_in_json(raw_text: str) -> str:
    try:
        return find_vendor_name_in_object(json.loads(raw_text))
    except json.JSONDecodeError:
        return ""


def find_vendor_name_in_object(value: object, depth: int = 0) -> str:
    if not value or depth > 2:
        return ""
    if isinstance(value, list):
        for item in value[:3]:
            match = find_vendor_name_in_object(item, depth + 1)
            if match:
                return match
        return ""
    if not isinstance(value, dict):
        return ""

    preferred_keys = [
        "vendor",
        "vendor_name",
        "vendorName",
        "supplier",
        "supplier_name",
        "supplierName",
        "provider",
        "provider_name",
        "providerName",
        "company",
        "company_name",
        "companyName",
        "organization",
        "organization_name",
        "organizationName",
    ]
    for key in preferred_keys:
        value_at_key = value.get(key)
        if isinstance(value_at_key, str) and value_at_key.strip():
            return value_at_key.strip()

    for nested_value in value.values():
        if isinstance(nested_value, (dict, list)):
            match = find_vendor_name_in_object(nested_value, depth + 1)
            if match:
                return match
    return ""


def find_vendor_name_in_csv(raw_text: str) -> str:
    if not raw_text.strip():
        return ""

    reader = csv.reader(io.StringIO(raw_text))
    rows = []
    for row in reader:
        cleaned = [cell.strip() for cell in row]
        if any(cleaned):
            rows.append(cleaned)
        if len(rows) >= 4:
            break

    if len(rows) < 2:
        return ""

    headers = [cell.lower() for cell in rows[0]]
    vendor_index = next(
        (index for index, cell in enumerate(headers) if re.search(r"vendor|supplier|provider|company|organization", cell)),
        -1,
    )
    if vendor_index >= 0 and vendor_index < len(rows[1]) and rows[1][vendor_index]:
        return rows[1][vendor_index].strip()

    if len(rows[0]) >= 2 and re.search(r"vendor|supplier|provider|company|organization", rows[0][0].lower()):
        return rows[0][1].strip()

    return ""


__all__ = [
    "SUPPORTED_POLICY_EXTENSIONS",
    "SUPPORTED_MAPPING_EXTENSIONS",
    "SUPPORTED_VENDOR_EXTENSIONS",
    "ValidationError",
    "file_extension",
    "file_name_base",
    "format_uploaded_policy_id",
    "upload_size_label",
    "validate_policy_upload_files",
    "validate_mapping_upload_file",
    "validate_vendor_upload_files",
    "decode_upload",
    "markdown_to_html",
    "extract_purpose_from_markdown",
    "sanitize_uploaded_html",
    "build_preview_text",
    "is_text_like_file",
    "summarize_vendor_survey",
    "infer_vendor_name",
]
