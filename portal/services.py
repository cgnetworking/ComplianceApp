from __future__ import annotations

import csv
import html
import io
import json
import re
import uuid
from datetime import date, datetime, timezone as dt_timezone

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from .models import PortalState, RiskRecord, UploadedPolicy, VendorResponse


SUPPORTED_POLICY_EXTENSIONS = {"md", "markdown", "txt", "html", "htm"}
TEXT_VENDOR_EXTENSIONS = {"csv", "json", "txt", "md", "markdown", "html", "htm", "xml"}
BLOCKED_TAGS_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|form|link|meta)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
BLOCKED_SINGLE_TAG_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|form|link|meta)\b[^>]*?/?>",
    re.IGNORECASE,
)
EVENT_HANDLER_RE = re.compile(r"\s+on[a-z0-9_-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
JAVASCRIPT_QUOTED_ATTR_RE = re.compile(
    r"""\s+(href|src)\s*=\s*(["'])\s*javascript:[^"']*\2""",
    re.IGNORECASE,
)
JAVASCRIPT_UNQUOTED_ATTR_RE = re.compile(r"\s+(href|src)\s*=\s*javascript:[^\s>]+", re.IGNORECASE)
PURPOSE_RE = re.compile(r"^## 1\. Purpose\s+([\s\S]*?)\s+## ", re.MULTILINE)


class ValidationError(Exception):
    pass


def get_bootstrap_payload() -> dict[str, object]:
    return {
        "persistenceMode": "api",
        "uploadedDocuments": [item.to_portal_dict() for item in UploadedPolicy.objects.all()],
        "vendorSurveyResponses": [item.to_portal_dict() for item in VendorResponse.objects.all()],
        "riskRegister": [item.to_portal_dict() for item in RiskRecord.objects.all()],
        "reviewState": normalize_review_state(get_state_payload("review_state", {})),
        "controlState": normalize_control_state(get_state_payload("control_state", {})),
    }


def get_state_payload(key: str, default: dict[str, object]) -> dict[str, object]:
    try:
        record = PortalState.objects.get(key=key)
    except PortalState.DoesNotExist:
        return default
    return record.payload if isinstance(record.payload, dict) else default


def set_state_payload(key: str, payload: dict[str, object]) -> dict[str, object]:
    record, _ = PortalState.objects.update_or_create(key=key, defaults={"payload": payload})
    return record.payload


def create_uploaded_policies(files: list[UploadedFile]) -> tuple[list[dict[str, object]], list[str]]:
    created_items: list[UploadedPolicy] = []
    messages: list[str] = []

    for uploaded_file in files:
        extension = file_extension(uploaded_file.name)
        if extension not in SUPPORTED_POLICY_EXTENSIONS:
            messages.append(
                f"{uploaded_file.name} was skipped because only markdown, text, and HTML files are supported."
            )
            continue

        raw_text = decode_upload(uploaded_file)
        content_html = sanitize_uploaded_html(raw_text) if extension in {"html", "htm"} else markdown_to_html(raw_text)
        policy = UploadedPolicy.objects.create(
            document_id=f"UPL-TEMP-{uuid.uuid4().hex[:12]}",
            title=file_name_base(uploaded_file.name),
            document_type="Uploaded policy",
            owner="Shared portal",
            approver="Pending review",
            review_frequency="Not scheduled",
            path=f"Portal upload / {uploaded_file.name}",
            folder="Uploaded",
            purpose=extract_purpose_from_markdown(raw_text) or f"Uploaded from {uploaded_file.name}.",
            content_html=content_html or "<p>No content was found in the uploaded file.</p>",
            raw_text=raw_text,
            original_filename=uploaded_file.name,
        )
        policy.document_id = format_uploaded_policy_id(policy.pk or 0)
        policy.save(update_fields=["document_id"])
        created_items.append(policy)

    if not created_items and messages:
        raise ValidationError(messages[0])

    return [item.to_portal_dict() for item in created_items], messages


def create_vendor_responses(files: list[UploadedFile]) -> list[dict[str, object]]:
    created_items: list[VendorResponse] = []

    for uploaded_file in files:
        extension = extract_file_extension(uploaded_file.name)
        raw_text = decode_upload(uploaded_file).replace("\x00", "").strip() if is_text_like_file(uploaded_file, extension) else ""
        preview_text = build_preview_text(raw_text, 1400, 20)
        response = VendorResponse.objects.create(
            external_id=f"vendor-{uuid.uuid4().hex[:16]}",
            vendor_name=infer_vendor_name(uploaded_file.name, raw_text, extension),
            file_name=uploaded_file.name,
            extension=extension or "file",
            mime_type=uploaded_file.content_type or "Unknown",
            file_size=uploaded_file.size or 0,
            preview_text=preview_text,
            summary=summarize_vendor_survey(uploaded_file.name, raw_text, extension, preview_text),
            status="Preview ready" if preview_text else "Metadata only",
            raw_text=raw_text,
        )
        created_items.append(response)

    return [item.to_portal_dict() for item in created_items]


def replace_risk_register(items: list[object]) -> list[dict[str, object]]:
    if not isinstance(items, list):
        raise ValidationError("Risk register payload must be a list.")

    identifiers: list[str] = []

    with transaction.atomic():
        for item in items:
            record = normalize_risk_record(item)
            identifiers.append(record["external_id"])
            RiskRecord.objects.update_or_create(
                external_id=record["external_id"],
                defaults={
                    "risk": record["risk"],
                    "initial_risk_level": record["initial_risk_level"],
                    "date": record["date"],
                    "owner": record["owner"],
                    "closed_date": record["closed_date"],
                    "created_at": record["created_at"],
                    "updated_at": record["updated_at"],
                },
            )

        if identifiers:
            RiskRecord.objects.exclude(external_id__in=identifiers).delete()
        else:
            RiskRecord.objects.all().delete()

    return [item.to_portal_dict() for item in RiskRecord.objects.all()]


def normalize_review_state(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {"activities": {}, "checklist": {}}
    activities = payload.get("activities") if isinstance(payload.get("activities"), dict) else {}
    checklist = payload.get("checklist") if isinstance(payload.get("checklist"), dict) else {}
    return {
        "activities": {str(key): bool(value) for key, value in activities.items()},
        "checklist": {str(key): bool(value) for key, value in checklist.items()},
    }


def normalize_control_state(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}

    normalized: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        excluded = bool(value.get("excluded"))
        reason = str(value.get("reason") or "")
        if excluded or reason:
            normalized[key] = {"excluded": excluded, "reason": reason}
    return normalized


def normalize_risk_record(item: object) -> dict[str, object]:
    if not isinstance(item, dict):
        raise ValidationError("Each risk record must be an object.")

    external_id = str(item.get("id") or "").strip()
    risk_text = str(item.get("risk") or "").strip()
    owner = str(item.get("owner") or "").strip()
    initial_risk_level = normalize_risk_level(item.get("initialRiskLevel"))
    raised_date = parse_iso_date(item.get("date"))
    closed_date = parse_optional_iso_date(item.get("closedDate"))
    created_at = parse_iso_datetime(item.get("createdAt"), fallback=timezone.now())
    updated_at = parse_iso_datetime(item.get("updatedAt"), fallback=timezone.now())

    if not external_id or not risk_text or not owner or not initial_risk_level or not raised_date:
        raise ValidationError("Each risk requires an id, description, owner, level, and date.")
    if closed_date and closed_date < raised_date:
        raise ValidationError("Risk closed date cannot be earlier than the raised date.")

    return {
        "external_id": external_id,
        "risk": risk_text,
        "owner": owner,
        "initial_risk_level": initial_risk_level,
        "date": raised_date,
        "closed_date": closed_date,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def parse_iso_date(value: object) -> date:
    if not value:
        raise ValidationError("Date is required.")
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise ValidationError("Invalid date value.") from error


def parse_optional_iso_date(value: object) -> date | None:
    if not value:
        return None
    return parse_iso_date(value)


def parse_iso_datetime(value: object, fallback: datetime) -> datetime:
    if not value:
        return fallback
    raw_value = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError as error:
        raise ValidationError("Invalid timestamp value.") from error
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def normalize_risk_level(value: object) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return 0
    return level if 1 <= level <= 5 else 0


def format_uploaded_policy_id(number: int) -> str:
    return f"UPL-{number:02d}"


def file_extension(file_name: str) -> str:
    parts = str(file_name).lower().split(".")
    return parts[-1] if len(parts) > 1 else ""


def file_name_base(file_name: str) -> str:
    without_extension = re.sub(r"\.[^.]+$", "", str(file_name))
    normalized = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", without_extension)).strip()
    return normalized or str(file_name)


def decode_upload(uploaded_file: UploadedFile) -> str:
    try:
        return uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        return uploaded_file.read().decode("utf-8", errors="replace")
    finally:
        uploaded_file.seek(0)


def inline_markup(text: str) -> str:
    rendered = html.escape(text)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", rendered)
    return rendered


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    cells = table_cells(stripped)
    return bool(cells) and all(cell and re.fullmatch(r"[-:]+", cell) for cell in cells)


def markdown_to_html(markdown: str) -> str:
    lines = str(markdown).splitlines()
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        line = re.sub(r"\s+$", "", lines[index])
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            header = table_cells(lines[index])
            index += 2
            body: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                body.append(table_cells(lines[index]))
                index += 1
            blocks.append(
                "<table><thead><tr>"
                + "".join(f"<th>{inline_markup(cell)}</th>" for cell in header)
                + "</tr></thead><tbody>"
                + "".join(
                    "<tr>" + "".join(f"<td>{inline_markup(cell)}</td>" for cell in row) + "</tr>"
                    for row in body
                )
                + "</tbody></table>"
            )
            continue

        if stripped.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(lines[index].strip()[2:])
                index += 1
            blocks.append("<ul>" + "".join(f"<li>{inline_markup(item)}</li>" for item in items) + "</ul>")
            continue

        if stripped.startswith("#"):
            level = min(len(re.match(r"^#+", stripped).group(0)), 6)
            blocks.append(f"<h{level}>{inline_markup(stripped[level:].strip())}</h{level}>")
            index += 1
            continue

        paragraph = [stripped]
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate:
                index += 1
                break
            if candidate.startswith("#") or candidate.startswith("- "):
                break
            if candidate.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
                break
            paragraph.append(candidate)
            index += 1
        blocks.append(f"<p>{inline_markup(' '.join(paragraph))}</p>")

    return "\n".join(blocks)


def extract_purpose_from_markdown(markdown: str) -> str:
    match = PURPOSE_RE.search(str(markdown))
    if not match:
        return ""
    return " ".join(line.strip() for line in match.group(1).splitlines() if line.strip())


def sanitize_uploaded_html(value: str) -> str:
    sanitized = BLOCKED_TAGS_RE.sub("", value)
    sanitized = BLOCKED_SINGLE_TAG_RE.sub("", sanitized)
    sanitized = EVENT_HANDLER_RE.sub("", sanitized)
    sanitized = JAVASCRIPT_QUOTED_ATTR_RE.sub("", sanitized)
    sanitized = JAVASCRIPT_UNQUOTED_ATTR_RE.sub("", sanitized)
    sanitized = sanitized.strip()
    return sanitized or f"<pre class=\"document-pre\">{html.escape(value)}</pre>"


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


def extract_file_extension(file_name: str) -> str:
    match = re.search(r"\.([^.]+)$", str(file_name))
    return match.group(1).lower() if match else ""


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
    return cleaned or derive_display_name(file_name) or "Unknown vendor"


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


def derive_display_name(file_name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", re.sub(r"\.[^.]+$", "", file_name))).strip()
