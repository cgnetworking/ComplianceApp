from __future__ import annotations

import csv
import html
import io
import json
import re
import uuid
from datetime import date, datetime, timezone as dt_timezone

import bleach
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from ..models import PortalState


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
EICAR_SIGNATURE = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
HTML_ALLOWED_TAGS = frozenset(
    {
        "a",
        "b",
        "blockquote",
        "br",
        "code",
        "dd",
        "div",
        "dl",
        "dt",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "li",
        "ol",
        "p",
        "pre",
        "s",
        "span",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "u",
        "ul",
    }
)
HTML_ALLOWED_ATTRIBUTES = {
    "*": ["class"],
    "a": ["href", "title", "target", "rel"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}
HTML_ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto"})
HTML_SANITIZER = bleach.sanitizer.Cleaner(
    tags=HTML_ALLOWED_TAGS,
    attributes=HTML_ALLOWED_ATTRIBUTES,
    protocols=HTML_ALLOWED_PROTOCOLS,
    strip=True,
    strip_comments=True,
)
PURPOSE_RE = re.compile(r"^## 1\. Purpose\s+([\s\S]*?)\s+## ", re.MULTILINE)
ANNEX_A_CONTROL_DOMAIN_BY_FAMILY = {
    "5": "Organizational",
    "6": "People",
    "7": "Physical",
    "8": "Technological",
}
ALLOWED_CONTROL_APPLICABILITY = {"Applicable", "Excluded"}
CSV_CONTROL_ID_FIELDS = ("controlid", "id", "control", "controlnumber", "annexacontrol")
CSV_CONTROL_NAME_FIELDS = ("controlname", "name", "controltitle")
CSV_CONTROL_DOMAIN_FIELDS = ("controldomain", "domain")
CSV_CONTROL_APPLICABILITY_FIELDS = ("controlapplicability", "applicability", "status")
CSV_CONTROL_OWNER_FIELDS = ("controlowner", "owner")
CSV_CONTROL_REVIEW_FREQUENCY_FIELDS = ("controlreviewfrequency", "reviewfrequency", "frequency")
CSV_DOCUMENT_IDS_FIELDS = ("policydocumentids", "documentids", "policyids", "documents", "mappedpolicies", "mappeddocuments")
CSV_DOCUMENT_ID_FIELDS = ("policydocumentid", "documentid", "policyid")
CSV_PREFERRED_DOCUMENT_ID_FIELDS = ("preferreddocumentid", "primarydocumentid", "defaultdocumentid")
CSV_DOCUMENT_TITLE_FIELDS = ("documenttitle", "policytitle", "doctitle")
CSV_DOCUMENT_TYPE_FIELDS = ("documenttype", "policytype")
CSV_DOCUMENT_OWNER_FIELDS = ("documentowner", "policyowner")
CSV_DOCUMENT_APPROVER_FIELDS = ("documentapprover", "policyapprover", "approver")
CSV_DOCUMENT_REVIEW_FREQUENCY_FIELDS = ("documentreviewfrequency", "policyreviewfrequency")
CSV_DOCUMENT_PATH_FIELDS = ("documentpath", "policypath")
CSV_DOCUMENT_FOLDER_FIELDS = ("documentfolder", "policyfolder")
CSV_DOCUMENT_PURPOSE_FIELDS = ("documentpurpose", "policypurpose")
POLICY_READER_GROUP_NAME = "Policy Reader"
PENDING_POLICY_APPROVER = "Pending review"
RISK_RECORD_MODEL_FIELDS = (
    "risk",
    "probability",
    "impact",
    "initial_risk_level",
    "date",
    "owner",
    "closed_date",
    "created_at",
    "updated_at",
)
BOOTSTRAP_PAGES = frozenset(
    {
        "home",
        "controls",
        "reviews",
        "review-tasks",
        "audit-log",
        "policies",
        "risks",
        "vendors",
        "assessments",
    }
)
BOOTSTRAP_PAGES_WITH_REVIEW_STATE = frozenset({"home", "reviews", "review-tasks", "audit-log"})
BOOTSTRAP_PAGES_WITH_CONTROL_STATE = frozenset({"home", "controls", "policies"})


class ValidationError(Exception):
    pass


def user_is_policy_reader(user: object) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if bool(getattr(user, "is_staff", False)):
        return False

    cached_value = getattr(user, "_portal_is_policy_reader", None)
    if isinstance(cached_value, bool):
        return cached_value

    groups = getattr(user, "groups", None)
    is_policy_reader = bool(groups and groups.filter(name=POLICY_READER_GROUP_NAME).exists())
    setattr(user, "_portal_is_policy_reader", is_policy_reader)
    return is_policy_reader


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


def normalize_iso_date_string(value: object) -> str:
    normalized = normalize_string(value)
    if not normalized:
        return ""
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError:
        return ""


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


def infer_control_domain(control_id: str, domain: str) -> str:
    if domain:
        return domain

    match = re.match(r"^\s*(?:A\.)?\s*(\d+)\b", control_id, flags=re.IGNORECASE)
    if not match:
        return ""
    return ANNEX_A_CONTROL_DOMAIN_BY_FAMILY.get(match.group(1), "")


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
        domain = infer_control_domain(control_id, normalize_string(item.get("domain")))

        controls.append(
            {
                "id": control_id,
                "name": normalize_string(item.get("name")),
                "domain": domain,
                "applicability": normalize_string(item.get("applicability")),
                "owner": normalize_string(item.get("owner")),
                "reviewFrequency": normalize_string(item.get("reviewFrequency"), "Annual"),
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
                "contentHtml": sanitize_uploaded_html(normalize_string(item.get("contentHtml"))),
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
                "startDate": normalize_iso_date_string(item.get("startDate")),
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
    if isinstance(payload, list):
        payload = {"controls": payload}
    elif not isinstance(payload, dict):
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


def normalize_csv_column_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def mapping_csv_lookup(row: dict[str, str], field_names: tuple[str, ...]) -> str:
    for field_name in field_names:
        candidate = normalize_string(row.get(field_name))
        if candidate:
            return candidate
    return ""


def split_mapping_csv_values(raw_value: str) -> list[str]:
    candidates = re.split(r"[\n,;|]+", str(raw_value))
    deduped: list[str] = []
    for candidate in candidates:
        normalized = normalize_string(candidate)
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def ensure_mapping_document_record(document_id: str, records: dict[str, dict[str, object]]) -> dict[str, object]:
    existing = records.get(document_id)
    if existing is not None:
        return existing

    created = {
        "id": document_id,
        "title": "",
        "type": "",
        "owner": "",
        "approver": "",
        "reviewFrequency": "",
        "path": "",
        "folder": "",
        "purpose": "",
        "contentHtml": "",
        "isUploaded": False,
        "originalFilename": "",
    }
    records[document_id] = created
    return created


def set_if_empty(item: dict[str, object], key: str, value: str) -> None:
    if value and not normalize_string(item.get(key)):
        item[key] = value


def parse_mapping_csv_text(value: str) -> dict[str, object]:
    reader = csv.DictReader(io.StringIO(value))
    if not reader.fieldnames:
        raise ValidationError("Uploaded mapping CSV must include a header row.")

    normalized_headers = {
        normalize_csv_column_name(header)
        for header in reader.fieldnames
        if normalize_csv_column_name(header)
    }
    if not normalized_headers.intersection(CSV_CONTROL_ID_FIELDS):
        raise ValidationError("Uploaded mapping CSV must include a control id column (for example: control_id or id).")

    controls_by_id: dict[str, dict[str, object]] = {}
    documents_by_id: dict[str, dict[str, object]] = {}
    parsed_rows = 0

    for raw_row in reader:
        row = {
            normalize_csv_column_name(key): normalize_string(raw_value)
            for key, raw_value in raw_row.items()
            if normalize_csv_column_name(key)
        }
        if not any(row.values()):
            continue
        parsed_rows += 1

        document_ids: list[str] = []
        for field_name in CSV_DOCUMENT_IDS_FIELDS:
            for value_item in split_mapping_csv_values(row.get(field_name, "")):
                if value_item not in document_ids:
                    document_ids.append(value_item)

        singular_document_id = mapping_csv_lookup(row, CSV_DOCUMENT_ID_FIELDS)
        if singular_document_id and singular_document_id not in document_ids:
            document_ids.append(singular_document_id)

        preferred_document_id = mapping_csv_lookup(row, CSV_PREFERRED_DOCUMENT_ID_FIELDS)
        if preferred_document_id and preferred_document_id not in document_ids:
            document_ids.append(preferred_document_id)

        control_id = mapping_csv_lookup(row, CSV_CONTROL_ID_FIELDS)
        if control_id:
            control = controls_by_id.get(control_id)
            if control is None:
                control = {
                    "id": control_id,
                    "name": mapping_csv_lookup(row, CSV_CONTROL_NAME_FIELDS),
                    "domain": mapping_csv_lookup(row, CSV_CONTROL_DOMAIN_FIELDS),
                    "applicability": mapping_csv_lookup(row, CSV_CONTROL_APPLICABILITY_FIELDS),
                    "owner": mapping_csv_lookup(row, CSV_CONTROL_OWNER_FIELDS),
                    "reviewFrequency": mapping_csv_lookup(row, CSV_CONTROL_REVIEW_FREQUENCY_FIELDS),
                    "documentIds": [],
                    "policyDocumentIds": [],
                    "preferredDocumentId": preferred_document_id,
                }
                controls_by_id[control_id] = control
            else:
                set_if_empty(control, "name", mapping_csv_lookup(row, CSV_CONTROL_NAME_FIELDS))
                set_if_empty(control, "domain", mapping_csv_lookup(row, CSV_CONTROL_DOMAIN_FIELDS))
                set_if_empty(control, "applicability", mapping_csv_lookup(row, CSV_CONTROL_APPLICABILITY_FIELDS))
                set_if_empty(control, "owner", mapping_csv_lookup(row, CSV_CONTROL_OWNER_FIELDS))
                set_if_empty(control, "reviewFrequency", mapping_csv_lookup(row, CSV_CONTROL_REVIEW_FREQUENCY_FIELDS))
                if preferred_document_id:
                    control["preferredDocumentId"] = preferred_document_id

            control_document_ids = control["documentIds"] if isinstance(control.get("documentIds"), list) else []
            for document_id in document_ids:
                if document_id not in control_document_ids:
                    control_document_ids.append(document_id)
            control["documentIds"] = control_document_ids
            control["policyDocumentIds"] = list(control_document_ids)

        for document_id in document_ids:
            ensure_mapping_document_record(document_id, documents_by_id)

        metadata_document_id = singular_document_id or (document_ids[0] if len(document_ids) == 1 else "")
        if metadata_document_id:
            document = ensure_mapping_document_record(metadata_document_id, documents_by_id)
            set_if_empty(document, "title", mapping_csv_lookup(row, CSV_DOCUMENT_TITLE_FIELDS))
            set_if_empty(document, "type", mapping_csv_lookup(row, CSV_DOCUMENT_TYPE_FIELDS))
            set_if_empty(document, "owner", mapping_csv_lookup(row, CSV_DOCUMENT_OWNER_FIELDS))
            set_if_empty(document, "approver", mapping_csv_lookup(row, CSV_DOCUMENT_APPROVER_FIELDS))
            set_if_empty(document, "reviewFrequency", mapping_csv_lookup(row, CSV_DOCUMENT_REVIEW_FREQUENCY_FIELDS))
            set_if_empty(document, "path", mapping_csv_lookup(row, CSV_DOCUMENT_PATH_FIELDS))
            set_if_empty(document, "folder", mapping_csv_lookup(row, CSV_DOCUMENT_FOLDER_FIELDS))
            set_if_empty(document, "purpose", mapping_csv_lookup(row, CSV_DOCUMENT_PURPOSE_FIELDS))

    if not parsed_rows:
        raise ValidationError("Uploaded mapping CSV is empty.")
    if not controls_by_id:
        raise ValidationError("Uploaded mapping CSV must include at least one control row.")

    for control in controls_by_id.values():
        document_ids = normalize_string_list(control.get("documentIds"))
        preferred_document_id = normalize_string(control.get("preferredDocumentId"))
        if preferred_document_id and preferred_document_id not in document_ids:
            document_ids.append(preferred_document_id)
        if not preferred_document_id and document_ids:
            preferred_document_id = document_ids[0]

        control["documentIds"] = document_ids
        control["policyDocumentIds"] = list(document_ids)
        control["preferredDocumentId"] = preferred_document_id
        for document_id in document_ids:
            ensure_mapping_document_record(document_id, documents_by_id)

    return {
        "controls": list(controls_by_id.values()),
        "documents": list(documents_by_id.values()),
    }


def parse_mapping_text(raw_text: str, extension: str) -> object:
    value = str(raw_text).strip().lstrip("\ufeff")
    if not value:
        raise ValidationError("Uploaded mapping file is empty.")

    if extension == "csv":
        return parse_mapping_csv_text(value)

    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise ValidationError("Uploaded mapping must be valid JSON when using a .json file.") from error


def get_state_payload(key: str, default: dict[str, object]) -> dict[str, object]:
    try:
        record = PortalState.objects.get(key=key)
    except PortalState.DoesNotExist:
        return default
    return record.payload if isinstance(record.payload, dict) else default


def set_state_payload(key: str, payload: dict[str, object]) -> dict[str, object]:
    record, _ = PortalState.objects.update_or_create(key=key, defaults={"payload": payload})
    return record.payload


def normalize_review_state_boolean_map(value: object) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    return {str(key).strip(): bool(item) for key, item in value.items() if str(key).strip()}


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


def normalize_review_state_timestamp_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key:
            continue
        raw_timestamp = str(raw_value or "").strip()
        if not raw_timestamp:
            continue
        try:
            normalized[key] = parse_iso_datetime(raw_timestamp, fallback=timezone.now()).isoformat()
        except ValidationError:
            continue
    return normalized


def normalize_audit_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, object] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key:
            continue
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            normalized[key] = raw_value
        else:
            normalized[key] = str(raw_value)
    return normalized


def normalize_review_state_audit_entry(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None

    action = normalize_string(value.get("action"), "state_changed")
    entity_type = normalize_string(value.get("entityType"), "record")
    entity_id = normalize_string(value.get("entityId"))
    summary = normalize_string(value.get("summary"), "State updated.")

    occurred_at_raw = value.get("occurredAt")
    try:
        occurred_at = parse_iso_datetime(occurred_at_raw, fallback=timezone.now()).isoformat()
    except ValidationError:
        occurred_at = timezone.now().isoformat()

    actor = value.get("actor") if isinstance(value.get("actor"), dict) else {}
    username = normalize_string(actor.get("username"), "system")
    display_name = normalize_string(actor.get("displayName"), username)

    fallback_seed = f"{action}|{entity_type}|{entity_id}|{occurred_at}"
    fallback_id = f"audit-{uuid.uuid5(uuid.NAMESPACE_URL, fallback_seed).hex[:12]}"

    return {
        "id": normalize_string(value.get("id"), fallback_id),
        "action": action,
        "entityType": entity_type,
        "entityId": entity_id,
        "summary": summary,
        "actor": {
            "username": username,
            "displayName": display_name,
        },
        "occurredAt": occurred_at,
        "metadata": normalize_audit_metadata(value.get("metadata")),
    }


def normalize_review_state_audit_log(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, object]] = []
    for entry in value:
        normalized_entry = normalize_review_state_audit_entry(entry)
        if normalized_entry is None:
            continue
        normalized.append(normalized_entry)
    return normalized[-2000:]


def parse_review_state_month_scope(state_key: str) -> tuple[int | None, str]:
    match = re.match(r"^m([0-9]|1[01])::(.+)$", state_key)
    if not match:
        return None, state_key
    return int(match.group(1)), str(match.group(2)).strip()


def build_review_done_audit_entry(
    state_key: str,
    *,
    actor_username: str,
    actor_display_name: str,
    occurred_at_iso: str,
) -> dict[str, object]:
    month_index, scoped_item_id = parse_review_state_month_scope(state_key)
    metadata: dict[str, object] = {
        "source": "reviews",
        "status": "done",
        "stateKey": state_key,
    }
    if month_index is not None:
        metadata["monthIndex"] = month_index
    if scoped_item_id:
        metadata["scopedItemId"] = scoped_item_id

    return {
        "id": f"audit-{uuid.uuid4().hex[:12]}",
        "action": "state_changed",
        "entityType": "task",
        "entityId": scoped_item_id or state_key,
        "summary": "State changed to done.",
        "actor": {
            "username": actor_username,
            "displayName": actor_display_name,
        },
        "occurredAt": occurred_at_iso,
        "metadata": metadata,
    }


def normalize_review_state(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {"activities": {}, "checklist": {}, "completedAt": {}, "auditLog": []}

    activities = normalize_review_state_boolean_map(payload.get("activities"))
    checklist = normalize_review_state_boolean_map(payload.get("checklist"))
    completed_at = normalize_review_state_timestamp_map(payload.get("completedAt"))
    audit_log_source = payload.get("auditLog") if isinstance(payload.get("auditLog"), list) else payload.get("events")
    audit_log = normalize_review_state_audit_log(audit_log_source)

    return {
        "activities": activities,
        "checklist": checklist,
        "completedAt": completed_at,
        "auditLog": audit_log,
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
        raw_applicability = str(value.get("applicability") or "").strip()
        applicability = raw_applicability if raw_applicability in ALLOWED_CONTROL_APPLICABILITY else ""
        review_frequency = str(value.get("reviewFrequency") or "").strip()
        owner = normalize_string(value.get("owner"))
        has_policy_document_override = isinstance(value.get("policyDocumentIds"), list)
        policy_document_ids: list[str] = []
        if has_policy_document_override:
            seen_policy_document_ids: set[str] = set()
            for item in value.get("policyDocumentIds", []):
                document_id = str(item or "").strip()
                if not document_id or document_id in seen_policy_document_ids:
                    continue
                seen_policy_document_ids.add(document_id)
                policy_document_ids.append(document_id)
        preferred_document_id = str(value.get("preferredDocumentId") or "").strip()
        if preferred_document_id and has_policy_document_override and preferred_document_id not in policy_document_ids:
            preferred_document_id = ""

        if excluded or reason or applicability or review_frequency or owner or has_policy_document_override or preferred_document_id:
            entry: dict[str, object] = {"excluded": excluded, "reason": reason}
            if applicability:
                entry["applicability"] = applicability
            if review_frequency:
                entry["reviewFrequency"] = review_frequency
            if owner:
                entry["owner"] = owner
            if has_policy_document_override:
                entry["policyDocumentIds"] = policy_document_ids
            if preferred_document_id:
                entry["preferredDocumentId"] = preferred_document_id
            normalized[key] = entry
    return normalized


def normalize_risk_factor(value: object) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return 0
    return level if 1 <= level <= 5 else 0


def normalize_risk_score(value: object) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return score if 1 <= score <= 25 else 0


def risk_factors_from_legacy_score(score: int) -> tuple[int, int]:
    if not score:
        return 0, 0
    if score <= 5:
        return score, score
    return closest_risk_factor_pair(score)


def closest_risk_factor_pair(score: int) -> tuple[int, int]:
    target = min(max(score, 1), 25)
    candidates: list[tuple[int, int, int, int, int, int]] = []
    for probability in range(1, 6):
        for impact in range(1, 6):
            product = probability * impact
            if product < target:
                continue
            candidates.append(
                (
                    product - target,
                    abs(probability - impact),
                    -product,
                    -max(probability, impact),
                    probability,
                    impact,
                )
            )
    if not candidates:
        return 5, 5
    best = min(candidates)
    return best[4], best[5]


def infer_missing_risk_factor(known_factor: int, score: int, fallback: int) -> int:
    if known_factor and score and score % known_factor == 0:
        derived = score // known_factor
        if 1 <= derived <= 5:
            return derived
    return fallback if 1 <= fallback <= 5 else 0


def resolve_risk_factors(probability: int, impact: int, legacy_score: int) -> tuple[int, int]:
    if probability and impact:
        return probability, impact
    if not legacy_score:
        return probability, impact

    fallback_probability, fallback_impact = risk_factors_from_legacy_score(legacy_score)
    if probability and not impact:
        impact = infer_missing_risk_factor(probability, legacy_score, fallback_impact)
    elif impact and not probability:
        probability = infer_missing_risk_factor(impact, legacy_score, fallback_probability)
    else:
        probability = fallback_probability if not probability else probability
        impact = fallback_impact if not impact else impact
    return probability, impact


def normalize_risk_record(item: object) -> dict[str, object]:
    if not isinstance(item, dict):
        raise ValidationError("Each risk record must be an object.")

    external_id = str(item.get("id") or "").strip()
    risk_text = str(item.get("risk") or "").strip()
    owner = str(item.get("owner") or "").strip()
    probability = normalize_risk_factor(item.get("probability"))
    impact = normalize_risk_factor(item.get("impact"))
    legacy_score = normalize_risk_score(item.get("initialRiskLevel"))
    probability, impact = resolve_risk_factors(probability, impact, legacy_score)
    initial_risk_level = probability * impact
    raised_date = parse_iso_date(item.get("date"))
    closed_date = parse_optional_iso_date(item.get("closedDate"))
    created_at = parse_iso_datetime(item.get("createdAt"), fallback=timezone.now())
    updated_at = parse_iso_datetime(item.get("updatedAt"), fallback=timezone.now())

    if not external_id or not risk_text or not owner or not probability or not impact or not raised_date:
        raise ValidationError("Each risk requires an id, description, owner, probability, impact, and date.")
    if closed_date and closed_date < raised_date:
        raise ValidationError("Risk closed date cannot be earlier than the raised date.")

    return {
        "external_id": external_id,
        "risk": risk_text,
        "owner": owner,
        "probability": probability,
        "impact": impact,
        "initial_risk_level": initial_risk_level,
        "date": raised_date,
        "closed_date": closed_date,
        "created_at": created_at,
        "updated_at": updated_at,
    }


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
            chunk_bytes = chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8", errors="replace")
            bytes_read += len(chunk_bytes)
            if max_bytes is not None and max_bytes > 0 and bytes_read > max_bytes:
                raise ValidationError(
                    f"{uploaded_file.name} exceeds the {upload_size_label(max_bytes)} upload limit."
                )
            chunks.append(chunk_bytes)
    finally:
        uploaded_file.seek(0)

    return b"".join(chunks)


def scan_uploaded_file(
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
    if bool(getattr(settings, "UPLOAD_SCANNING_ENABLED", True)) and EICAR_SIGNATURE in payload.upper():
        raise ValidationError(f"{uploaded_file.name} failed upload scanning.")


def validate_policy_upload_files(files: list[UploadedFile]) -> None:
    max_files = int(getattr(settings, "POLICY_UPLOAD_MAX_FILES", 20))
    if len(files) > max_files:
        raise ValidationError(f"Upload up to {max_files} policy file(s) at a time.")

    max_bytes = int(getattr(settings, "POLICY_UPLOAD_MAX_FILE_BYTES", 2097152))
    for uploaded_file in files:
        extension = file_extension(uploaded_file.name)
        if extension not in SUPPORTED_POLICY_EXTENSIONS:
            continue
        scan_uploaded_file(uploaded_file, max_bytes=max_bytes, expect_text=True)


def validate_mapping_upload_file(file_obj: UploadedFile) -> None:
    extension = file_extension(file_obj.name)
    if extension not in SUPPORTED_MAPPING_EXTENSIONS:
        raise ValidationError("Upload a JSON or CSV mapping file (.json, .csv).")
    scan_uploaded_file(
        file_obj,
        max_bytes=int(getattr(settings, "MAPPING_UPLOAD_MAX_FILE_BYTES", 5242880)),
        expect_text=True,
    )


def validate_vendor_upload_files(files: list[UploadedFile]) -> None:
    max_files = int(getattr(settings, "VENDOR_UPLOAD_MAX_FILES", 25))
    if len(files) > max_files:
        raise ValidationError(f"Upload up to {max_files} vendor response file(s) at a time.")

    max_bytes = int(getattr(settings, "VENDOR_UPLOAD_MAX_FILE_BYTES", 10485760))
    allowed_extensions = ", ".join(sorted(SUPPORTED_VENDOR_EXTENSIONS))
    for uploaded_file in files:
        extension = file_extension(uploaded_file.name)
        if extension not in SUPPORTED_VENDOR_EXTENSIONS:
            raise ValidationError(
                f"{uploaded_file.name} is not a supported vendor upload type. Allowed extensions: {allowed_extensions}."
            )
        scan_uploaded_file(uploaded_file, max_bytes=max_bytes, expect_text=extension in TEXT_VENDOR_EXTENSIONS)


def decode_upload(uploaded_file: UploadedFile, *, max_bytes: int | None = None) -> str:
    payload = read_upload_bytes(uploaded_file, max_bytes=max_bytes)
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload.decode("utf-8", errors="replace")


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
    raw_html = str(value or "")
    sanitized = HTML_SANITIZER.clean(raw_html).strip()
    if sanitized:
        return sanitized
    if not raw_html.strip():
        return ""
    return f"<pre class=\"document-pre\">{html.escape(raw_html)}</pre>"


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
