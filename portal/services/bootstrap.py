from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from ..authorization import (
    PortalAction,
    PortalResource,
    has_portal_permission,
)
from ..models import PortalState, ReviewChecklistItem
from .common import (
    BOOTSTRAP_PAGES,
    BOOTSTRAP_PAGES_WITH_CONTROL_STATE,
    BOOTSTRAP_PAGES_WITH_REVIEW_STATE,
    ValidationError,
    build_review_done_audit_entry,
    get_state_payload,
    normalize_control_state,
    normalize_review_state,
    normalize_review_state_audit_log,
    normalize_audit_metadata,
    normalize_string,
    parse_optional_iso_date,
    parse_review_state_month_scope,
    set_state_payload,
)
from .policies import (
    get_mapping_bootstrap_payload,
    list_review_checklist_items,
    list_review_checklist_recommendations,
    list_uploaded_documents,
    list_vendor_responses,
)
from .risks import list_risk_register


def normalize_bootstrap_page(value: object) -> str:
    normalized = normalize_string(value).lower()
    return normalized if normalized in BOOTSTRAP_PAGES else ""


def serialize_assignable_user(user: object) -> dict[str, str] | None:
    user_model = get_user_model()
    username_field = getattr(user_model, "USERNAME_FIELD", "username")
    username = normalize_string(getattr(user, username_field, ""))
    if not username:
        return None
    first_name = normalize_string(getattr(user, "first_name", ""))
    last_name = normalize_string(getattr(user, "last_name", ""))
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    email = normalize_string(getattr(user, "email", ""))
    return {"username": username, "displayName": full_name or email or username}


def list_assignable_users() -> list[dict[str, str]]:
    user_model = get_user_model()
    username_field = getattr(user_model, "USERNAME_FIELD", "username")
    assignable_users: list[dict[str, str]] = []
    for user in user_model.objects.filter(is_active=True).order_by(username_field):
        serialized_user = serialize_assignable_user(user)
        if serialized_user is None:
            continue
        assignable_users.append(serialized_user)
    return assignable_users


def list_assignable_users_for_viewer(viewer: object | None, *, page: str = "") -> list[dict[str, str]]:
    if not getattr(viewer, "is_authenticated", False):
        return []
    if bool(getattr(viewer, "is_staff", False)):
        return list_assignable_users()
    if page != "risks":
        return []

    serialized_user = serialize_assignable_user(viewer)
    return [serialized_user] if serialized_user is not None else []


def review_state_payload_template(payload: dict[str, object] | None = None) -> dict[str, object]:
    source = payload if isinstance(payload, dict) else {}
    return {
        "activities": source.get("activities", {}),
        "checklist": source.get("checklist", {}),
        "completedAt": source.get("completedAt", {}),
        "auditLog": source.get("auditLog", []),
    }


def append_review_state_audit_entries(entries: list[object]) -> dict[str, object]:
    normalized_entries = normalize_review_state_audit_log(entries)
    if not normalized_entries:
        return normalize_review_state(get_state_payload("review_state", {}))

    with transaction.atomic():
        record, _ = PortalState.objects.select_for_update().get_or_create(
            key="review_state",
            defaults={"payload": review_state_payload_template(normalize_review_state({}))},
        )
        previous_state = normalize_review_state(record.payload)
        existing_audit_log = previous_state.get("auditLog") if isinstance(previous_state.get("auditLog"), list) else []
        next_state = review_state_payload_template(previous_state)
        next_state["auditLog"] = normalize_review_state_audit_log(existing_audit_log + normalized_entries)
        record.payload = next_state
        record.save(update_fields=["payload", "updated_at"])
        return next_state


def build_portal_audit_entry(
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    actor_username: str,
    actor_display_name: str,
    metadata: dict[str, object] | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, object]:
    normalized_action = normalize_string(action).replace(" ", "_").lower()
    normalized_entity_type = normalize_string(entity_type).replace(" ", "_").lower()
    normalized_entity_id = normalize_string(entity_id)
    normalized_summary = normalize_string(summary)
    normalized_actor_username = normalize_string(actor_username)
    normalized_actor_display_name = normalize_string(actor_display_name)
    if not normalized_action or not normalized_entity_type or not normalized_summary or not normalized_actor_username:
        raise ValidationError("Audit entries require action, entityType, summary, and actor_username.")
    timestamp = occurred_at or timezone.now()
    if timezone.is_naive(timestamp):
        timestamp = timezone.make_aware(timestamp, timezone=dt_timezone.utc)

    return {
        "id": f"audit-{uuid.uuid4().hex[:12]}",
        "action": normalized_action,
        "entityType": normalized_entity_type,
        "entityId": normalized_entity_id,
        "summary": normalized_summary,
        "actor": {
            "username": normalized_actor_username,
            "displayName": normalized_actor_display_name,
        },
        "occurredAt": timestamp.isoformat(),
        "metadata": normalize_audit_metadata(metadata or {}),
    }


def append_portal_audit_entry(
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    actor_username: str,
    actor_display_name: str,
    metadata: dict[str, object] | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, object]:
    return append_review_state_audit_entries(
        [
            build_portal_audit_entry(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                summary=summary,
                actor_username=actor_username,
                actor_display_name=actor_display_name,
                metadata=metadata,
                occurred_at=occurred_at,
            )
        ]
    )


def build_policy_approval_audit_entry(
    policy: object,
    *,
    actor_username: str,
    actor_display_name: str,
    occurred_at: datetime,
) -> dict[str, object]:
    local_approval_time = timezone.localtime(occurred_at)
    approval_date = f"{local_approval_time.strftime('%B')} {local_approval_time.day}, {local_approval_time.year}"
    return {
        "id": f"audit-{uuid.uuid4().hex[:12]}",
        "action": "policy_approved",
        "entityType": "policy",
        "entityId": policy.document_id,
        "summary": f"Approved {policy.document_id} / {policy.title} on {approval_date}.",
        "actor": {
            "username": actor_username,
            "displayName": actor_display_name,
        },
        "occurredAt": occurred_at.isoformat(),
        "metadata": {
            "source": "policies",
            "policyId": policy.document_id,
            "policyTitle": policy.title,
            "approvedBy": actor_username,
            "approvedAt": occurred_at.isoformat(),
        },
    }


def create_review_checklist_item(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValidationError("Checklist item payload must be an object.")

    item_text = normalize_string(payload.get("item"))
    if not item_text:
        raise ValidationError("Checklist item text is required.")

    category = normalize_string(payload.get("category"))
    frequency = normalize_string(payload.get("frequency"))
    start_date = parse_optional_iso_date(payload.get("startDate"))
    owner = normalize_string(payload.get("owner"))
    if not category or not frequency or not owner:
        raise ValidationError("Checklist items require category, frequency, and owner.")

    for _ in range(5):
        external_id = f"checklist-{uuid.uuid4().hex[:12]}"
        if not ReviewChecklistItem.objects.filter(external_id=external_id).exists():
            created = ReviewChecklistItem.objects.create(
                external_id=external_id,
                category=category,
                item=item_text,
                frequency=frequency,
                start_date=start_date,
                owner=owner,
            )
            return created.to_portal_dict()

    raise ValidationError("Unable to create checklist item id. Retry the request.")


def delete_review_checklist_item(external_id: str) -> dict[str, str]:
    normalized_id = normalize_string(external_id)
    if not normalized_id:
        raise ValidationError("Checklist item id is required.")

    try:
        checklist_item = ReviewChecklistItem.objects.get(external_id=normalized_id)
    except ReviewChecklistItem.DoesNotExist as error:
        raise ValidationError("Checklist item was not found.") from error

    deleted_item = checklist_item.to_portal_dict()
    checklist_item.delete()

    review_state = normalize_review_state(get_state_payload("review_state", {}))
    checklist_state = review_state.get("checklist") if isinstance(review_state.get("checklist"), dict) else {}
    activity_state = review_state.get("activities") if isinstance(review_state.get("activities"), dict) else {}
    completed_at_state = review_state.get("completedAt") if isinstance(review_state.get("completedAt"), dict) else {}
    audit_log = review_state.get("auditLog") if isinstance(review_state.get("auditLog"), list) else []

    def keep_state_entry(key: str) -> bool:
        return key != normalized_id and not key.endswith(f"::{normalized_id}")

    filtered_checklist_state = {str(key): bool(value) for key, value in checklist_state.items() if keep_state_entry(str(key))}
    filtered_activity_state = {str(key): bool(value) for key, value in activity_state.items() if keep_state_entry(str(key))}
    filtered_completed_at_state = {
        str(key): str(value)
        for key, value in completed_at_state.items()
        if keep_state_entry(str(key))
    }

    if (
        filtered_checklist_state != checklist_state
        or filtered_activity_state != activity_state
        or filtered_completed_at_state != completed_at_state
    ):
        set_state_payload(
            "review_state",
            {
                "activities": filtered_activity_state,
                "checklist": filtered_checklist_state,
                "completedAt": filtered_completed_at_state,
                "auditLog": audit_log,
            },
        )

    return deleted_item


def done_review_state_keys(payload: dict[str, object]) -> set[str]:
    checklist = payload.get("checklist") if isinstance(payload.get("checklist"), dict) else {}
    activities = payload.get("activities") if isinstance(payload.get("activities"), dict) else {}
    keys = set(checklist.keys()) | set(activities.keys())
    return {key for key in keys if bool(checklist.get(key)) or bool(activities.get(key))}


def update_review_state(
    payload: object,
    *,
    actor_username: str,
    actor_display_name: str,
) -> dict[str, object]:
    previous_state = normalize_review_state(get_state_payload("review_state", {}))
    incoming_state = normalize_review_state(payload)

    previous_done_keys = done_review_state_keys(previous_state)
    next_done_keys = done_review_state_keys(incoming_state)
    previous_completed_at = previous_state.get("completedAt") if isinstance(previous_state.get("completedAt"), dict) else {}
    incoming_completed_at = incoming_state.get("completedAt") if isinstance(incoming_state.get("completedAt"), dict) else {}

    next_completed_at: dict[str, str] = {}
    new_entries: list[dict[str, object]] = []
    now_iso = timezone.now().isoformat()

    for key in sorted(next_done_keys):
        if key in previous_done_keys:
            existing_timestamp = ""
            previous_timestamp = previous_completed_at.get(key)
            incoming_timestamp = incoming_completed_at.get(key)
            if isinstance(previous_timestamp, str) and previous_timestamp.strip():
                existing_timestamp = previous_timestamp.strip()
            elif isinstance(incoming_timestamp, str) and incoming_timestamp.strip():
                existing_timestamp = incoming_timestamp.strip()
            if existing_timestamp:
                next_completed_at[key] = existing_timestamp
            continue

        next_completed_at[key] = now_iso
        new_entries.append(
            build_review_done_audit_entry(
                key,
                actor_username=actor_username,
                actor_display_name=actor_display_name,
                occurred_at_iso=now_iso,
            )
        )

    existing_audit_log = previous_state.get("auditLog") if isinstance(previous_state.get("auditLog"), list) else []
    merged_audit_log = normalize_review_state_audit_log(existing_audit_log + new_entries)

    normalized = {
        "activities": incoming_state.get("activities", {}),
        "checklist": incoming_state.get("checklist", {}),
        "completedAt": next_completed_at,
        "auditLog": merged_audit_log,
    }
    set_state_payload("review_state", normalized)
    return normalized


def review_state_payload_for_viewer(review_state: object, *, viewer: object | None) -> dict[str, object]:
    normalized = normalize_review_state(review_state)
    can_view_review_state = has_portal_permission(viewer, PortalResource.REVIEW_STATE, PortalAction.VIEW)
    can_view_audit_log = has_portal_permission(viewer, PortalResource.AUDIT_LOG, PortalAction.VIEW)

    return {
        "activities": normalized.get("activities", {}) if can_view_review_state else {},
        "checklist": normalized.get("checklist", {}) if can_view_review_state else {},
        "completedAt": normalized.get("completedAt", {}) if can_view_review_state else {},
        "auditLog": normalized.get("auditLog", []) if can_view_audit_log else [],
    }


def get_bootstrap_payload(*, viewer: object | None = None, policy_reader: bool = False, page: str = "") -> dict[str, object]:
    normalized_page = normalize_bootstrap_page(page)
    include_all_sections = normalized_page == ""
    include_document_content = include_all_sections

    can_view_mapping = has_portal_permission(viewer, PortalResource.MAPPING, PortalAction.VIEW)
    can_view_policy_documents = has_portal_permission(viewer, PortalResource.POLICY_DOCUMENT, PortalAction.VIEW)
    can_view_review_state = has_portal_permission(viewer, PortalResource.REVIEW_STATE, PortalAction.VIEW)
    can_view_audit_log = has_portal_permission(viewer, PortalResource.AUDIT_LOG, PortalAction.VIEW)
    can_view_control_state = has_portal_permission(viewer, PortalResource.CONTROL_STATE, PortalAction.VIEW)
    can_view_vendor_responses = has_portal_permission(viewer, PortalResource.VENDOR_RESPONSE, PortalAction.VIEW)
    can_view_risks = has_portal_permission(viewer, PortalResource.RISK_RECORD, PortalAction.VIEW)

    payload: dict[str, object] = {"persistenceMode": "api"}
    if can_view_mapping:
        payload["mapping"] = get_mapping_bootstrap_payload(include_document_content=include_document_content)
    if can_view_policy_documents:
        payload["uploadedDocuments"] = list_uploaded_documents(include_content=include_document_content, viewer=viewer)

    assignable_users = list_assignable_users_for_viewer(viewer, page=normalized_page)
    if assignable_users:
        payload["assignableUsers"] = assignable_users
    if include_all_sections or normalized_page in BOOTSTRAP_PAGES_WITH_REVIEW_STATE:
        if can_view_review_state:
            payload["checklistItems"] = list_review_checklist_items(viewer=viewer)
            payload["recommendedChecklistItems"] = list_review_checklist_recommendations(viewer=viewer)
        if can_view_review_state or can_view_audit_log:
            payload["reviewState"] = review_state_payload_for_viewer(
                get_state_payload("review_state", {}),
                viewer=viewer,
            )
    if include_all_sections or normalized_page in BOOTSTRAP_PAGES_WITH_CONTROL_STATE:
        if can_view_control_state:
            payload["controlState"] = normalize_control_state(get_state_payload("control_state", {}))
    if include_all_sections and can_view_vendor_responses:
        payload["vendorSurveyResponses"] = list_vendor_responses(viewer=viewer)
    if (include_all_sections or normalized_page == "risks") and can_view_risks:
        payload["riskRegister"] = list_risk_register(viewer=viewer)
    return payload


__all__ = [
    "normalize_bootstrap_page",
    "list_assignable_users",
    "review_state_payload_template",
    "append_review_state_audit_entries",
    "build_portal_audit_entry",
    "append_portal_audit_entry",
    "build_policy_approval_audit_entry",
    "create_review_checklist_item",
    "delete_review_checklist_item",
    "done_review_state_keys",
    "update_review_state",
    "review_state_payload_for_viewer",
    "get_bootstrap_payload",
    "ValidationError",
]
