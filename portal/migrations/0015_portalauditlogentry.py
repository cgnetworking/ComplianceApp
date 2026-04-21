from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.db import migrations, models
from django.utils import timezone


def parse_audit_occurrence(value):
    raw_value = str(value or "").strip().replace("Z", "+00:00")
    if not raw_value:
        return timezone.now()
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        return timezone.now()
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def migrate_review_state_audit_log(apps, schema_editor):
    PortalAuditLogEntry = apps.get_model("portal", "PortalAuditLogEntry")
    PortalState = apps.get_model("portal", "PortalState")

    for review_state in PortalState.objects.filter(key="review_state").iterator():
        payload = review_state.payload if isinstance(review_state.payload, dict) else {}
        raw_entries = payload.get("auditLog")
        if isinstance(raw_entries, list):
            for entry in raw_entries:
                if not isinstance(entry, dict):
                    continue
                actor = entry.get("actor") if isinstance(entry.get("actor"), dict) else {}
                metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
                audit_id = str(entry.get("id") or "").strip()
                action = str(entry.get("action") or "").strip()
                entity_type = str(entry.get("entityType") or "").strip()
                summary = str(entry.get("summary") or "").strip()
                actor_username = str(actor.get("username") or "").strip()
                if not audit_id or not action or not entity_type or not summary or not actor_username:
                    continue
                PortalAuditLogEntry.objects.update_or_create(
                    external_id=audit_id,
                    defaults={
                        "action": action,
                        "entity_type": entity_type,
                        "entity_id": str(entry.get("entityId") or "").strip(),
                        "summary": summary,
                        "actor_username": actor_username,
                        "actor_display_name": str(actor.get("displayName") or "").strip(),
                        "occurred_at": parse_audit_occurrence(entry.get("occurredAt")),
                        "metadata": metadata,
                    },
                )

        if "auditLog" in payload:
            review_state.payload = {key: value for key, value in payload.items() if key != "auditLog"}
            review_state.save(update_fields=["payload", "updated_at"])


def restore_review_state_audit_log(apps, schema_editor):
    PortalAuditLogEntry = apps.get_model("portal", "PortalAuditLogEntry")
    PortalState = apps.get_model("portal", "PortalState")

    review_state, _ = PortalState.objects.get_or_create(key="review_state", defaults={"payload": {}})
    payload = review_state.payload if isinstance(review_state.payload, dict) else {}
    payload["auditLog"] = [
        {
            "id": entry.external_id,
            "action": entry.action,
            "entityType": entry.entity_type,
            "entityId": entry.entity_id,
            "summary": entry.summary,
            "actor": {
                "username": entry.actor_username,
                "displayName": entry.actor_display_name,
            },
            "occurredAt": entry.occurred_at.isoformat(),
            "metadata": entry.metadata if isinstance(entry.metadata, dict) else {},
        }
        for entry in PortalAuditLogEntry.objects.order_by("occurred_at", "id")
    ]
    review_state.payload = payload
    review_state.save(update_fields=["payload", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0014_seed_portal_member_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalAuditLogEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=64, unique=True)),
                ("action", models.CharField(max_length=120)),
                ("entity_type", models.CharField(max_length=120)),
                ("entity_id", models.CharField(blank=True, default="", max_length=255)),
                ("summary", models.TextField()),
                ("actor_username", models.CharField(max_length=255)),
                ("actor_display_name", models.CharField(blank=True, default="", max_length=255)),
                ("occurred_at", models.DateTimeField(db_index=True, default=timezone.now)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-occurred_at", "-id"],
            },
        ),
        migrations.RunPython(migrate_review_state_audit_log, restore_review_state_audit_log),
    ]
