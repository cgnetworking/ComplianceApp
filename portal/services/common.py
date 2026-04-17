from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import date, datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from ..models import PortalState
from .html_sanitization import sanitize_uploaded_html


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


def coerce_non_negative_int(value: object) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Expected a non-negative integer value.") from None
    if normalized < 0:
        raise ValidationError("Expected a non-negative integer value.")
    return normalized


def normalize_string(value: object) -> str:
    if value is None:
        return ""
    normalized = str(value).strip()
    return normalized


def normalize_iso_date_string(value: object) -> str:
    normalized = normalize_string(value)
    if not normalized:
        return ""
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as error:
        raise ValidationError("Invalid ISO date value.") from error


def normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_mapping_timestamp(value: object) -> str:
    if value is None:
        return timezone.now().isoformat()
    if not isinstance(value, str):
        raise ValidationError("Mapping generatedAt must be a timestamp string.")
    raw_value = value.strip().replace("Z", "+00:00")
    if not raw_value:
        raise ValidationError("Mapping generatedAt is required.")
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError as error:
        raise ValidationError("Mapping generatedAt must be a valid timestamp.") from error
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed.isoformat()


def normalize_mapping_source_snapshot(value: object) -> dict[str, object]:
    if value is None:
        value = {}
    elif not isinstance(value, dict):
        raise ValidationError("Mapping sourceSnapshot must be an object.")
    return {
        "controlRegister": normalize_string(value.get("controlRegister")),
        "reviewSchedule": normalize_string(value.get("reviewSchedule")),
        "runtimeDependency": bool(value.get("runtimeDependency")),
    }


def normalize_mapping_controls(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValidationError("Mapping controls must be a list.")

    controls: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("Each mapping control must be an object.")

        control_id = normalize_string(item.get("id"))
        if not control_id:
            raise ValidationError("Each mapping control requires an id.")

        document_ids = normalize_string_list(item.get("documentIds"))
        policy_document_ids = normalize_string_list(item.get("policyDocumentIds"))
        preferred_document_id = normalize_string(item.get("preferredDocumentId"))
        if preferred_document_id and preferred_document_id not in policy_document_ids:
            raise ValidationError("Mapping preferredDocumentId must be included in policyDocumentIds.")
        domain = normalize_string(item.get("domain"))

        controls.append(
            {
                "id": control_id,
                "name": normalize_string(item.get("name")),
                "domain": domain,
                "applicability": normalize_string(item.get("applicability")),
                "owner": normalize_string(item.get("owner")),
                "reviewFrequency": normalize_string(item.get("reviewFrequency")),
                "documentIds": document_ids,
                "policyDocumentIds": policy_document_ids,
                "preferredDocumentId": preferred_document_id,
            }
        )
    return controls


def normalize_mapping_documents(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValidationError("Mapping documents must be a list.")

    documents: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("Each mapping document must be an object.")

        document_id = normalize_string(item.get("id"))
        if not document_id:
            raise ValidationError("Each mapping document requires an id.")

        title = normalize_string(item.get("title"))
        if not title:
            raise ValidationError(f"Mapping document {document_id} requires a title.")
        documents.append(
            {
                "id": document_id,
                "title": title,
                "type": normalize_string(item.get("type")),
                "owner": normalize_string(item.get("owner")),
                "approver": normalize_string(item.get("approver")),
                "reviewFrequency": normalize_string(item.get("reviewFrequency")),
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
        raise ValidationError("Mapping activities must be a list.")

    activities: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("Each mapping activity must be an object.")

        activity_id = normalize_string(item.get("id"))
        if not activity_id:
            raise ValidationError("Each mapping activity requires an id.")

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
        raise ValidationError("Mapping checklist must be a list.")

    checklist_items: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("Each mapping checklist item must be an object.")

        checklist_id = normalize_string(item.get("id"))
        if not checklist_id:
            raise ValidationError("Each mapping checklist item requires an id.")

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
        raise ValidationError("Mapping policyCoverage must be a list.")

    titles = {item["id"]: item["title"] for item in documents if isinstance(item.get("id"), str)}
    coverage: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("Each mapping policy coverage entry must be an object.")

        document_id = normalize_string(item.get("id"))
        if not document_id:
            raise ValidationError("Each mapping policy coverage entry requires an id.")

        title = normalize_string(item.get("title"))
        if not title:
            raise ValidationError(f"Policy coverage entry {document_id} requires a title.")

        coverage.append(
            {
                "id": document_id,
                "title": title,
                "controlCount": coerce_non_negative_int(item.get("controlCount")),
                "reviewFrequency": normalize_string(item.get("reviewFrequency")),
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

    controls = normalize_mapping_controls(payload.get("controls", []))
    documents = normalize_mapping_documents(payload.get("documents", []))
    activities = normalize_mapping_activities(payload.get("activities", []))
    checklist_items = normalize_mapping_checklist(payload.get("checklist", []))
    policy_coverage_source = payload.get("policyCoverage")
    if policy_coverage_source is None:
        policy_coverage = build_mapping_policy_coverage(controls, documents)
    else:
        policy_coverage = normalize_mapping_policy_coverage(policy_coverage_source, documents)

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


def parse_iso_datetime(value: object) -> datetime:
    if not value:
        raise ValidationError("Timestamp is required.")
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
        raw_timestamp = normalize_string(raw_value)
        if not raw_timestamp:
            continue
        normalized[key] = parse_iso_datetime(raw_timestamp).isoformat()
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

    audit_id = normalize_string(value.get("id"))
    action = normalize_string(value.get("action"))
    entity_type = normalize_string(value.get("entityType"))
    entity_id = normalize_string(value.get("entityId"))
    summary = normalize_string(value.get("summary"))
    occurred_at = parse_iso_datetime(value.get("occurredAt")).isoformat()

    actor = value.get("actor") if isinstance(value.get("actor"), dict) else {}
    username = normalize_string(actor.get("username"))
    display_name = normalize_string(actor.get("displayName"))
    if not audit_id or not action or not entity_type or not summary or not username:
        raise ValidationError("Audit log entries require id, action, entityType, summary, and actor.username.")

    return {
        "id": audit_id,
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
    audit_log = normalize_review_state_audit_log(payload.get("auditLog"))

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
        reason = normalize_string(value.get("reason"))
        raw_applicability = normalize_string(value.get("applicability"))
        applicability = raw_applicability if raw_applicability in ALLOWED_CONTROL_APPLICABILITY else ""
        review_frequency = normalize_string(value.get("reviewFrequency"))
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
        if reason and applicability != "Excluded":
            raise ValidationError("Control exclusion reason requires applicability 'Excluded'.")

        if reason or applicability or review_frequency or owner or has_policy_document_override or preferred_document_id:
            entry: dict[str, object] = {"reason": reason}
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
