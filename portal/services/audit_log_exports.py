from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from .common import ValidationError, get_state_payload, normalize_review_state, parse_iso_datetime


AUDIT_LOG_EXPORT_HEADERS = (
    "id",
    "action",
    "entity_type",
    "entity_id",
    "summary",
    "occurred_at",
    "actor_username",
    "actor_display_name",
    "metadata_json",
)
_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)


def _parse_occurred_at(value: object) -> datetime:
    try:
        return parse_iso_datetime(value, fallback=_EPOCH_UTC)
    except ValidationError:
        return _EPOCH_UTC


def _normalize_audit_log_row(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None

    actor = value.get("actor") if isinstance(value.get("actor"), dict) else {}
    metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}

    return {
        "id": str(value.get("id") or "").strip(),
        "action": str(value.get("action") or "").strip(),
        "entity_type": str(value.get("entityType") or "").strip(),
        "entity_id": str(value.get("entityId") or "").strip(),
        "summary": str(value.get("summary") or "").strip(),
        "occurred_at": str(value.get("occurredAt") or "").strip(),
        "actor_username": str(actor.get("username") or "").strip(),
        "actor_display_name": str(actor.get("displayName") or "").strip(),
        "metadata_json": json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    }


def list_review_state_audit_log_entries() -> list[dict[str, object]]:
    review_state = normalize_review_state(get_state_payload("review_state", {}))
    audit_log = review_state.get("auditLog") if isinstance(review_state.get("auditLog"), list) else []

    rows: list[dict[str, object]] = []
    for entry in audit_log:
        normalized = _normalize_audit_log_row(entry)
        if normalized is None:
            continue
        rows.append(normalized)

    rows.sort(
        key=lambda entry: (_parse_occurred_at(entry.get("occurred_at")), str(entry.get("id") or "")),
        reverse=True,
    )
    return rows


def build_review_state_audit_log_csv(entries: list[dict[str, object]] | None = None) -> str:
    rows = entries if entries is not None else list_review_state_audit_log_entries()
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(AUDIT_LOG_EXPORT_HEADERS)
    for row in rows:
        writer.writerow(
            [
                row.get("id", ""),
                row.get("action", ""),
                row.get("entity_type", ""),
                row.get("entity_id", ""),
                row.get("summary", ""),
                row.get("occurred_at", ""),
                row.get("actor_username", ""),
                row.get("actor_display_name", ""),
                row.get("metadata_json", "{}"),
            ]
        )
    return buffer.getvalue()


def build_review_state_audit_log_export_filename(now: datetime | None = None) -> str:
    export_time = timezone.localtime(now or timezone.now())
    return f"audit_log_export_{export_time.strftime('%Y%m%d_%H%M%S')}.csv"


def build_review_state_audit_log_export(now: datetime | None = None) -> tuple[str, str]:
    csv_content = build_review_state_audit_log_csv()
    return build_review_state_audit_log_export_filename(now=now), csv_content


__all__ = [
    "AUDIT_LOG_EXPORT_HEADERS",
    "list_review_state_audit_log_entries",
    "build_review_state_audit_log_csv",
    "build_review_state_audit_log_export_filename",
    "build_review_state_audit_log_export",
]
