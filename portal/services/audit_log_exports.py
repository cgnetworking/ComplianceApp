from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from django.utils import timezone

from .audit_log import list_portal_audit_log_entries
from .common import parse_iso_datetime


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
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _escape_csv_formula(value: object) -> str:
    normalized = "" if value is None else str(value)
    if normalized.startswith(_CSV_FORMULA_PREFIXES):
        return f"'{normalized}"
    return normalized


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


def list_portal_audit_log_export_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in list_portal_audit_log_entries():
        normalized = _normalize_audit_log_row(entry)
        if normalized is None:
            continue
        rows.append(normalized)

    rows.sort(
        key=lambda entry: (parse_iso_datetime(entry.get("occurred_at")), str(entry.get("id") or "")),
        reverse=True,
    )
    return rows


def build_portal_audit_log_csv(entries: list[dict[str, object]] | None = None) -> str:
    rows = entries if entries is not None else list_portal_audit_log_export_rows()
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(AUDIT_LOG_EXPORT_HEADERS)
    for row in rows:
        writer.writerow(
            [
                _escape_csv_formula(row.get("id", "")),
                _escape_csv_formula(row.get("action", "")),
                _escape_csv_formula(row.get("entity_type", "")),
                _escape_csv_formula(row.get("entity_id", "")),
                _escape_csv_formula(row.get("summary", "")),
                _escape_csv_formula(row.get("occurred_at", "")),
                _escape_csv_formula(row.get("actor_username", "")),
                _escape_csv_formula(row.get("actor_display_name", "")),
                _escape_csv_formula(row.get("metadata_json", "{}")),
            ]
        )
    return buffer.getvalue()


def build_portal_audit_log_export_filename(now: datetime | None = None) -> str:
    export_time = timezone.localtime(now or timezone.now())
    return f"audit_log_export_{export_time.strftime('%Y%m%d_%H%M%S')}.csv"


def build_portal_audit_log_export(now: datetime | None = None) -> tuple[str, str]:
    csv_content = build_portal_audit_log_csv()
    return build_portal_audit_log_export_filename(now=now), csv_content


__all__ = [
    "AUDIT_LOG_EXPORT_HEADERS",
    "list_portal_audit_log_export_rows",
    "build_portal_audit_log_csv",
    "build_portal_audit_log_export_filename",
    "build_portal_audit_log_export",
]
