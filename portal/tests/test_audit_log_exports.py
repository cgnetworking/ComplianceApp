from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from portal.models import PortalAuditLogEntry
from portal.services.audit_log_exports import (
    AUDIT_LOG_EXPORT_HEADERS,
    build_portal_audit_log_csv,
    build_portal_audit_log_export,
    list_portal_audit_log_export_rows,
)


class AuditLogExportTests(TestCase):
    def test_list_portal_audit_log_export_rows_orders_latest_first(self) -> None:
        PortalAuditLogEntry.objects.create(
            external_id="audit-001",
            action="state_changed",
            entity_type="task",
            entity_id="checklist-001",
            summary="Older entry",
            occurred_at="2026-04-14T08:00:00+00:00",
            actor_username="alice",
            actor_display_name="Alice",
            metadata={"source": "reviews", "monthIndex": 4},
        )
        PortalAuditLogEntry.objects.create(
            external_id="audit-002",
            action="policy_approved",
            entity_type="policy",
            entity_id="POL-001",
            summary="Latest entry",
            occurred_at="2026-04-15T08:00:00+00:00",
            actor_username="bob",
            actor_display_name="Bob",
            metadata={"policyId": "POL-001", "source": "policies"},
        )

        rows = list_portal_audit_log_export_rows()
        self.assertEqual([row["id"] for row in rows], ["audit-002", "audit-001"])
        self.assertEqual(rows[0]["actor_username"], "bob")
        self.assertEqual(rows[1]["actor_display_name"], "Alice")

    def test_build_portal_audit_log_csv_serializes_expected_columns(self) -> None:
        PortalAuditLogEntry.objects.create(
            external_id="audit-100",
            action="state_changed",
            entity_type="task",
            entity_id="checklist-100",
            summary="Completed task",
            occurred_at="2026-04-15T09:30:00+00:00",
            actor_username="charlie",
            actor_display_name="Charlie",
            metadata={"source": "reviews", "monthIndex": 3},
        )

        csv_text = build_portal_audit_log_csv()
        reader = csv.DictReader(io.StringIO(csv_text))
        self.assertEqual(reader.fieldnames, list(AUDIT_LOG_EXPORT_HEADERS))
        rows = list(reader)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "audit-100")
        self.assertEqual(rows[0]["action"], "state_changed")
        self.assertEqual(rows[0]["actor_display_name"], "Charlie")
        self.assertEqual(rows[0]["occurred_at"], "2026-04-15T09:30:00+00:00")
        self.assertEqual(json.loads(rows[0]["metadata_json"]), {"monthIndex": 3, "source": "reviews"})

    def test_build_portal_audit_log_export_returns_filename_and_csv(self) -> None:
        local_timezone = timezone.get_current_timezone()
        now = timezone.make_aware(datetime(2026, 4, 16, 14, 5, 6), local_timezone)

        file_name, csv_text = build_portal_audit_log_export(now=now)

        self.assertEqual(file_name, "audit_log_export_20260416_140506.csv")
        parsed_rows = list(csv.reader(io.StringIO(csv_text)))
        self.assertEqual(parsed_rows[0], list(AUDIT_LOG_EXPORT_HEADERS))

    def test_build_portal_audit_log_csv_escapes_formula_like_cells(self) -> None:
        PortalAuditLogEntry.objects.create(
            external_id="=cmd",
            action="+run",
            entity_type="@user",
            entity_id="-identifier",
            summary="=2+2",
            occurred_at="2026-04-15T09:30:00+00:00",
            actor_username="=alice",
            actor_display_name="+Alice",
            metadata={"source": "reviews"},
        )

        csv_text = build_portal_audit_log_csv()
        rows = list(csv.DictReader(io.StringIO(csv_text)))

        self.assertEqual(rows[0]["id"], "'=cmd")
        self.assertEqual(rows[0]["action"], "'+run")
        self.assertEqual(rows[0]["entity_type"], "'@user")
        self.assertEqual(rows[0]["entity_id"], "'-identifier")
        self.assertEqual(rows[0]["summary"], "'=2+2")
        self.assertEqual(rows[0]["actor_username"], "'=alice")
        self.assertEqual(rows[0]["actor_display_name"], "'+Alice")

    def test_audit_log_entries_are_immutable(self) -> None:
        entry = PortalAuditLogEntry.objects.create(
            external_id="audit-immutable",
            action="state_changed",
            entity_type="task",
            entity_id="checklist-immutable",
            summary="Immutable entry",
            occurred_at="2026-04-15T09:30:00+00:00",
            actor_username="alice",
            actor_display_name="Alice",
            metadata={"source": "reviews"},
        )

        entry.summary = "Updated entry"
        with self.assertRaises(ValidationError):
            entry.save()
        with self.assertRaises(ValidationError):
            entry.delete()
