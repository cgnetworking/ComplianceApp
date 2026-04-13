from __future__ import annotations

import csv
import html
import io
import json
import re
import uuid
from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from .models import (
    PortalState,
    ReviewChecklistItem,
    ReviewChecklistRecommendation,
    RiskRecord,
    UploadedPolicy,
    VendorResponse,
)


SUPPORTED_POLICY_EXTENSIONS = {"md", "markdown", "txt", "html", "htm"}
SUPPORTED_MAPPING_EXTENSIONS = {"json", "js"}
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
MAPPING_ASSIGNMENT_RE = re.compile(r"^\s*window\.ISMS_DATA\s*=\s*", re.IGNORECASE)


class ValidationError(Exception):
    pass


def default_mapping_summary() -> dict[str, object]:
    return {
        "controlCount": 0,
        "documentCount": 0,
        "policyCount": 0,
        "activityCount": 0,
        "checklistCount": 0,
        "domainCounts": {},
        "documentReviewFrequencies": {},
        "checklistFrequencies": {},
    }


def default_mapping_payload() -> dict[str, object]:
    return {
        "generatedAt": timezone.now().isoformat(),
        "sourceSnapshot": {
            "controlRegister": "",
            "reviewSchedule": "",
            "runtimeDependency": False,
        },
        "summary": default_mapping_summary(),
        "controls": [],
        "documents": [],
        "activities": [],
        "checklist": [],
        "policyCoverage": [],
    }


def coerce_non_negative_int(value: object, default: int = 0) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return default
    return normalized if normalized >= 0 else default


def normalize_string(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    normalized = str(value).strip()
    return normalized if normalized else fallback


def normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_mapping_timestamp(value: object) -> str:
    if isinstance(value, str):
        raw_value = value.strip().replace("Z", "+00:00")
        if raw_value:
            try:
                parsed = datetime.fromisoformat(raw_value)
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, dt_timezone.utc)
                return parsed.isoformat()
            except ValueError:
                pass
    return timezone.now().isoformat()


def normalize_mapping_source_snapshot(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        value = {}
    return {
        "controlRegister": normalize_string(value.get("controlRegister")),
        "reviewSchedule": normalize_string(value.get("reviewSchedule")),
        "runtimeDependency": bool(value.get("runtimeDependency")),
    }


def normalize_mapping_controls(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []

    controls: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        control_id = normalize_string(item.get("id"))
        if not control_id:
            continue

        document_ids = normalize_string_list(item.get("documentIds"))
        policy_document_ids = normalize_string_list(item.get("policyDocumentIds")) or document_ids
        preferred_document_id = normalize_string(item.get("preferredDocumentId"))
        if not preferred_document_id and policy_document_ids:
            preferred_document_id = policy_document_ids[0]

        controls.append(
            {
                "id": control_id,
                "name": normalize_string(item.get("name")),
                "domain": normalize_string(item.get("domain")),
                "applicability": normalize_string(item.get("applicability"), "Applicable"),
                "implementationModel": normalize_string(item.get("implementationModel"), "Implemented"),
                "owner": normalize_string(item.get("owner")),
                "reviewFrequency": normalize_string(item.get("reviewFrequency"), "Annual"),
                "rationale": normalize_string(item.get("rationale")),
                "evidence": normalize_string(item.get("evidence")),
                "documentIds": document_ids,
                "policyDocumentIds": policy_document_ids,
                "preferredDocumentId": preferred_document_id,
            }
        )
    return controls


def normalize_mapping_documents(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []

    documents: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        document_id = normalize_string(item.get("id"))
        if not document_id:
            continue

        title = normalize_string(item.get("title")) or document_id
        documents.append(
            {
                "id": document_id,
                "title": title,
                "type": normalize_string(item.get("type")),
                "owner": normalize_string(item.get("owner")),
                "approver": normalize_string(item.get("approver")),
                "reviewFrequency": normalize_string(item.get("reviewFrequency"), "Not scheduled"),
                "path": normalize_string(item.get("path")),
                "folder": normalize_string(item.get("folder")),
                "purpose": normalize_string(item.get("purpose")),
                "contentHtml": normalize_string(item.get("contentHtml")),
                "isUploaded": bool(item.get("isUploaded")),
                "originalFilename": normalize_string(item.get("originalFilename")),
            }
        )
    return documents


def normalize_mapping_activities(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []

    activities: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        activity_id = normalize_string(item.get("id"))
        if not activity_id:
            continue

        activities.append(
            {
                "id": activity_id,
                "month": normalize_string(item.get("month")),
                "monthIndex": coerce_non_negative_int(item.get("monthIndex")),
                "frequency": normalize_string(item.get("frequency")),
                "activity": normalize_string(item.get("activity")),
                "owner": normalize_string(item.get("owner")),
                "evidence": normalize_string(item.get("evidence")),
            }
        )
    return activities


def normalize_mapping_checklist(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []

    checklist_items: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        checklist_id = normalize_string(item.get("id"))
        if not checklist_id:
            continue

        checklist_items.append(
            {
                "id": checklist_id,
                "category": normalize_string(item.get("category")),
                "item": normalize_string(item.get("item")),
                "frequency": normalize_string(item.get("frequency")),
                "owner": normalize_string(item.get("owner")),
            }
        )
    return checklist_items


def normalize_mapping_policy_coverage(value: object, documents: list[dict[str, object]]) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []

    titles = {item["id"]: item["title"] for item in documents if isinstance(item.get("id"), str)}
    coverage: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        document_id = normalize_string(item.get("id"))
        if not document_id:
            continue

        coverage.append(
            {
                "id": document_id,
                "title": normalize_string(item.get("title")) or titles.get(document_id, document_id),
                "controlCount": coerce_non_negative_int(item.get("controlCount")),
                "reviewFrequency": normalize_string(item.get("reviewFrequency"), "Not scheduled"),
            }
        )
    return coverage


def build_mapping_policy_coverage(
    controls: list[dict[str, object]],
    documents: list[dict[str, object]],
) -> list[dict[str, object]]:
    titles = {item["id"]: item["title"] for item in documents if isinstance(item.get("id"), str)}
    review_frequencies = {
        item["id"]: item["reviewFrequency"]
        for item in documents
        if isinstance(item.get("id"), str) and isinstance(item.get("reviewFrequency"), str)
    }
    counts: dict[str, int] = {}

    for control in controls:
        if not isinstance(control, dict):
            continue
        document_ids = normalize_string_list(control.get("policyDocumentIds")) or normalize_string_list(control.get("documentIds"))
        for document_id in document_ids:
            counts[document_id] = counts.get(document_id, 0) + 1

    rows: list[dict[str, object]] = []
    for document_id in sorted(counts.keys()):
        rows.append(
            {
                "id": document_id,
                "title": titles.get(document_id, document_id),
                "controlCount": counts[document_id],
                "reviewFrequency": review_frequencies.get(document_id, "Not scheduled"),
            }
        )
    return rows


def build_mapping_summary(
    controls: list[dict[str, object]],
    documents: list[dict[str, object]],
    activities: list[dict[str, object]],
    checklist_items: list[dict[str, object]],
) -> dict[str, object]:
    domain_counts: dict[str, int] = {}
    for control in controls:
        if not isinstance(control, dict):
            continue
        domain = normalize_string(control.get("domain"))
        if not domain:
            continue
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    document_review_frequencies: dict[str, int] = {}
    for document in documents:
        if not isinstance(document, dict):
            continue
        frequency = normalize_string(document.get("reviewFrequency"))
        if not frequency:
            continue
        document_review_frequencies[frequency] = document_review_frequencies.get(frequency, 0) + 1

    checklist_frequencies: dict[str, int] = {}
    for item in checklist_items:
        if not isinstance(item, dict):
            continue
        frequency = normalize_string(item.get("frequency"))
        if not frequency:
            continue
        checklist_frequencies[frequency] = checklist_frequencies.get(frequency, 0) + 1

    policy_count = len({item["id"] for item in documents if re.fullmatch(r"(POL|GOV|PR|UPL)-\d+", str(item.get("id", "")), re.IGNORECASE)})

    return {
        "controlCount": len(controls),
        "documentCount": len(documents),
        "policyCount": policy_count,
        "activityCount": len(activities),
        "checklistCount": len(checklist_items),
        "domainCounts": domain_counts,
        "documentReviewFrequencies": document_review_frequencies,
        "checklistFrequencies": checklist_frequencies,
    }


def normalize_mapping_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        payload = {}

    controls = normalize_mapping_controls(payload.get("controls"))
    documents = normalize_mapping_documents(payload.get("documents"))
    activities = normalize_mapping_activities(payload.get("activities"))
    checklist_items = normalize_mapping_checklist(payload.get("checklist"))
    policy_coverage = normalize_mapping_policy_coverage(payload.get("policyCoverage"), documents)
    if not policy_coverage:
        policy_coverage = build_mapping_policy_coverage(controls, documents)

    normalized_payload = default_mapping_payload()
    normalized_payload.update(
        {
            "generatedAt": normalize_mapping_timestamp(payload.get("generatedAt")),
            "sourceSnapshot": normalize_mapping_source_snapshot(payload.get("sourceSnapshot")),
            "summary": build_mapping_summary(controls, documents, activities, checklist_items),
            "controls": controls,
            "documents": documents,
            "activities": activities,
            "checklist": checklist_items,
            "policyCoverage": policy_coverage,
        }
    )
    return normalized_payload


def parse_mapping_text(raw_text: str) -> object:
    value = str(raw_text).strip().lstrip("\ufeff")
    if not value:
        raise ValidationError("Uploaded mapping file is empty.")

    if MAPPING_ASSIGNMENT_RE.match(value):
        value = MAPPING_ASSIGNMENT_RE.sub("", value, count=1).strip()
        if value.endswith(";"):
            value = value[:-1].strip()

    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise ValidationError("Uploaded mapping must be valid JSON or a window.ISMS_DATA assignment.") from error


def replace_mapping_payload(file: UploadedFile) -> dict[str, object]:
    extension = file_extension(file.name)
    if extension not in SUPPORTED_MAPPING_EXTENSIONS:
        raise ValidationError("Upload a JSON mapping file (.json) or data snapshot file (.js).")

    parsed_payload = parse_mapping_text(decode_upload(file))
    normalized_payload = normalize_mapping_payload(parsed_payload)
    set_state_payload("mapping_state", normalized_payload)
    return normalized_payload


def get_mapping_payload() -> dict[str, object]:
    payload = get_state_payload("mapping_state", {})
    return normalize_mapping_payload(payload)


def get_bundled_mapping_payload() -> dict[str, object]:
    data_path = Path(__file__).resolve().parent.parent / "webapp" / "data.js"
    try:
        raw_text = data_path.read_text(encoding="utf-8")
    except OSError:
        return default_mapping_payload()

    try:
        parsed = parse_mapping_text(raw_text)
    except ValidationError:
        return default_mapping_payload()
    return normalize_mapping_payload(parsed)


def list_review_checklist_items() -> list[dict[str, str]]:
    return [item.to_portal_dict() for item in ReviewChecklistItem.objects.all()]


def list_review_checklist_recommendations() -> list[dict[str, str]]:
    return [item.to_portal_dict() for item in ReviewChecklistRecommendation.objects.all()]


def ensure_review_checklist_recommendations_seeded() -> None:
    if ReviewChecklistRecommendation.objects.exists():
        return

    mapping_payload = get_mapping_payload()
    checklist_items = normalize_mapping_checklist(mapping_payload.get("checklist"))
    if not checklist_items:
        checklist_items = normalize_mapping_checklist(get_bundled_mapping_payload().get("checklist"))
    if not checklist_items:
        return

    seen_ids: set[str] = set()
    to_create: list[ReviewChecklistRecommendation] = []
    for item in checklist_items:
        item_id = normalize_string(item.get("id"))
        item_text = normalize_string(item.get("item"))
        if not item_id or not item_text or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        to_create.append(
            ReviewChecklistRecommendation(
                external_id=item_id,
                category=normalize_string(item.get("category"), "Custom"),
                item=item_text,
                frequency=normalize_string(item.get("frequency"), "Annual"),
                owner=normalize_string(item.get("owner"), "Shared portal"),
            )
        )

    if to_create:
        ReviewChecklistRecommendation.objects.bulk_create(to_create, ignore_conflicts=True)


def create_review_checklist_item(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValidationError("Checklist item payload must be an object.")

    item_text = normalize_string(payload.get("item"))
    if not item_text:
        raise ValidationError("Checklist item text is required.")

    category = normalize_string(payload.get("category"), "Custom")
    frequency = normalize_string(payload.get("frequency"), "Annual")
    owner = normalize_string(payload.get("owner"), "Shared portal")

    for _ in range(5):
        external_id = f"checklist-{uuid.uuid4().hex[:12]}"
        if not ReviewChecklistItem.objects.filter(external_id=external_id).exists():
            created = ReviewChecklistItem.objects.create(
                external_id=external_id,
                category=category,
                item=item_text,
                frequency=frequency,
                owner=owner,
            )
            return created.to_portal_dict()

    raise ValidationError("Unable to create checklist item id. Retry the request.")


def get_bootstrap_payload() -> dict[str, object]:
    ensure_review_checklist_recommendations_seeded()
    return {
        "persistenceMode": "api",
        "mapping": get_mapping_payload(),
        "checklistItems": list_review_checklist_items(),
        "recommendedChecklistItems": list_review_checklist_recommendations(),
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


def delete_uploaded_policy(document_id: str) -> dict[str, object]:
    normalized_id = normalize_string(document_id)
    if not normalized_id:
        raise ValidationError("Policy id is required.")

    try:
        policy = UploadedPolicy.objects.get(document_id=normalized_id)
    except UploadedPolicy.DoesNotExist as error:
        raise ValidationError("Uploaded policy was not found.") from error

    deleted_payload = policy.to_portal_dict()
    policy.delete()
    return deleted_payload


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
        applicability = str(value.get("applicability") or "").strip()
        if excluded or reason or applicability:
            entry: dict[str, object] = {"excluded": excluded, "reason": reason}
            if applicability:
                entry["applicability"] = applicability
            normalized[key] = entry
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
