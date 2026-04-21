from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone

from ..authorization import (
    PortalAction,
    PortalResource,
    has_portal_permission,
)
from ..models import ReviewChecklistItem
from .audit_log import (
    append_portal_audit_entries,
    append_portal_audit_entry,
    audit_log_payload_for_viewer,
    build_policy_approval_audit_entry,
    build_portal_audit_entry,
    build_review_done_audit_entry,
)
from .common import (
    BOOTSTRAP_PAGES,
    BOOTSTRAP_PAGES_WITH_CONTROL_STATE,
    BOOTSTRAP_PAGES_WITH_REVIEW_STATE,
    ValidationError,
    get_state_payload,
    normalize_control_state,
    normalize_review_state,
    normalize_string,
    parse_optional_iso_date,
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
from .user_directory import list_assignable_users_for_viewer, resolve_assignable_username


def normalize_bootstrap_page(value: object) -> str:
    normalized = normalize_string(value).lower()
    return normalized if normalized in BOOTSTRAP_PAGES else ""


def create_review_checklist_item(payload: object, *, viewer: object | None = None) -> dict[str, str]:
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
    resolved_owner = resolve_assignable_username(owner, viewer=viewer, page="reviews")
    if not resolved_owner:
        raise ValidationError("Checklist item owner must be selected from an active user.")

    for _ in range(5):
        external_id = f"checklist-{uuid.uuid4().hex[:12]}"
        if not ReviewChecklistItem.objects.filter(external_id=external_id).exists():
            created = ReviewChecklistItem.objects.create(
                external_id=external_id,
                category=category,
                item=item_text,
                frequency=frequency,
                start_date=start_date,
                owner=resolved_owner,
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
    with transaction.atomic():
        previous_state = normalize_review_state(get_state_payload("review_state", {}))
        incoming_state = normalize_review_state(payload)

        previous_done_keys = done_review_state_keys(previous_state)
        next_done_keys = done_review_state_keys(incoming_state)
        previous_completed_at = (
            previous_state.get("completedAt") if isinstance(previous_state.get("completedAt"), dict) else {}
        )
        incoming_completed_at = (
            incoming_state.get("completedAt") if isinstance(incoming_state.get("completedAt"), dict) else {}
        )

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

        normalized = {
            "activities": incoming_state.get("activities", {}),
            "checklist": incoming_state.get("checklist", {}),
            "completedAt": next_completed_at,
        }
        set_state_payload("review_state", normalized)
        append_portal_audit_entries(new_entries)
        return normalized


def review_state_payload_for_viewer(review_state: object, *, viewer: object | None) -> dict[str, object]:
    normalized = normalize_review_state(review_state)
    can_view_review_state = has_portal_permission(viewer, PortalResource.REVIEW_STATE, PortalAction.VIEW)

    return {
        "activities": normalized.get("activities", {}) if can_view_review_state else {},
        "checklist": normalized.get("checklist", {}) if can_view_review_state else {},
        "completedAt": normalized.get("completedAt", {}) if can_view_review_state else {},
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
            payload["reviewState"] = review_state_payload_for_viewer(
                get_state_payload("review_state", {}),
                viewer=viewer,
            )
        if can_view_audit_log:
            payload["auditLog"] = audit_log_payload_for_viewer(viewer=viewer)
    if include_all_sections or normalized_page in BOOTSTRAP_PAGES_WITH_CONTROL_STATE:
        if can_view_control_state:
            payload["controlState"] = normalize_control_state(get_state_payload("control_state", {}), strict=False)
    if include_all_sections and can_view_vendor_responses:
        payload["vendorSurveyResponses"] = list_vendor_responses(viewer=viewer)
    if (include_all_sections or normalized_page == "risks") and can_view_risks:
        payload["riskRegister"] = list_risk_register(viewer=viewer)
    return payload


__all__ = [
    "normalize_bootstrap_page",
    "list_assignable_users_for_viewer",
    "build_portal_audit_entry",
    "append_portal_audit_entry",
    "append_portal_audit_entries",
    "audit_log_payload_for_viewer",
    "build_policy_approval_audit_entry",
    "create_review_checklist_item",
    "delete_review_checklist_item",
    "done_review_state_keys",
    "update_review_state",
    "review_state_payload_for_viewer",
    "get_bootstrap_payload",
    "ValidationError",
]
