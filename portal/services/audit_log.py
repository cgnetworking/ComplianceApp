from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

from django.db import transaction
from django.utils import timezone

from ..authorization import PortalAction, PortalResource, has_portal_permission
from ..models import PortalAuditLogEntry
from .common import (
    ValidationError,
    normalize_audit_metadata,
    normalize_string,
    parse_iso_datetime,
    parse_review_state_month_scope,
)


def normalize_portal_audit_entry(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValidationError("Audit entries must be objects.")

    audit_id = normalize_string(value.get("id"))
    action = normalize_string(value.get("action"))
    entity_type = normalize_string(value.get("entityType"))
    entity_id = normalize_string(value.get("entityId"))
    summary = normalize_string(value.get("summary"))
    occurred_at = parse_iso_datetime(value.get("occurredAt"))
    actor = value.get("actor") if isinstance(value.get("actor"), dict) else {}
    actor_username = normalize_string(actor.get("username"))
    actor_display_name = normalize_string(actor.get("displayName"))

    if not audit_id or not action or not entity_type or not summary or not actor_username:
        raise ValidationError("Audit entries require id, action, entityType, summary, and actor.username.")

    return {
        "id": audit_id,
        "action": action,
        "entityType": entity_type,
        "entityId": entity_id,
        "summary": summary,
        "actor": {
            "username": actor_username,
            "displayName": actor_display_name,
        },
        "occurredAt": occurred_at.isoformat(),
        "metadata": normalize_audit_metadata(value.get("metadata")),
    }


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
        "entityId": str(policy.document_id),
        "summary": f"Approved {policy.document_id} / {policy.title} on {approval_date}.",
        "actor": {
            "username": normalize_string(actor_username),
            "displayName": normalize_string(actor_display_name),
        },
        "occurredAt": occurred_at.isoformat(),
        "metadata": {
            "source": "policies",
            "policyId": str(policy.document_id),
            "policyTitle": str(policy.title),
            "approvedBy": normalize_string(actor_username),
            "approvedAt": occurred_at.isoformat(),
        },
    }


def append_portal_audit_entries(entries: list[object]) -> list[dict[str, object]]:
    normalized_entries = [normalize_portal_audit_entry(entry) for entry in entries]
    if not normalized_entries:
        return []

    created_entries: list[PortalAuditLogEntry] = []
    with transaction.atomic():
        for entry in normalized_entries:
            actor = entry["actor"]
            created_entries.append(
                PortalAuditLogEntry.objects.create(
                    external_id=str(entry["id"]),
                    action=str(entry["action"]),
                    entity_type=str(entry["entityType"]),
                    entity_id=str(entry["entityId"]),
                    summary=str(entry["summary"]),
                    actor_username=str(actor["username"]),
                    actor_display_name=str(actor["displayName"]),
                    occurred_at=parse_iso_datetime(entry["occurredAt"]),
                    metadata=dict(entry["metadata"]) if isinstance(entry["metadata"], dict) else {},
                )
            )
    return [entry.to_portal_dict() for entry in created_entries]


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
    created_entries = append_portal_audit_entries(
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
    return created_entries[0]


def list_portal_audit_log_entries() -> list[dict[str, object]]:
    return [entry.to_portal_dict() for entry in PortalAuditLogEntry.objects.all()]


def audit_log_payload_for_viewer(*, viewer: object | None) -> list[dict[str, object]]:
    if not has_portal_permission(viewer, PortalResource.AUDIT_LOG, PortalAction.VIEW):
        return []
    return list_portal_audit_log_entries()


__all__ = [
    "normalize_portal_audit_entry",
    "build_portal_audit_entry",
    "build_review_done_audit_entry",
    "build_policy_approval_audit_entry",
    "append_portal_audit_entries",
    "append_portal_audit_entry",
    "list_portal_audit_log_entries",
    "audit_log_payload_for_viewer",
]
