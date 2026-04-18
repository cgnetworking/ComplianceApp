from __future__ import annotations

import csv
import io
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from portal.authorization import PortalAction, PortalResource
from portal.services.risk_csv import serialize_risk_records_to_csv
from portal.tests.permissions import grant_user_permissions


class RiskMutationTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="risk-user", password="password")
        grant_user_permissions(
            self.user,
            (PortalResource.RISK_RECORD, PortalAction.VIEW),
            (PortalResource.RISK_RECORD, PortalAction.ADD),
            (PortalResource.RISK_RECORD, PortalAction.CHANGE),
            (PortalResource.RISK_RECORD, PortalAction.DELETE),
            (PortalResource.RISK_RECORD, PortalAction.EXPORT),
        )
        self.client.force_login(self.user)

    def risk_payload(
        self,
        risk_id: str,
        risk_text: str,
        *,
        probability: int = 3,
        impact: int = 3,
        created_by: str = "",
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": risk_id,
            "risk": risk_text,
            "probability": probability,
            "impact": impact,
            "date": "2026-01-10",
            "owner": "Risk Owner",
        }
        if created_by:
            payload["createdBy"] = created_by
        return payload

    def create_risk(self, risk_id: str, risk_text: str, *, created_by: str = "") -> None:
        response = self.client.post(
            "/api/risks/",
            data=json.dumps({"risk": self.risk_payload(risk_id, risk_text, created_by=created_by)}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

    def test_bulk_put_upserts_without_deleting_unsubmitted_rows(self) -> None:
        self.create_risk("risk-1", "Original risk one")
        self.create_risk("risk-2", "Original risk two")

        response = self.client.put(
            "/api/risks/",
            data=json.dumps({"riskRegister": [self.risk_payload("risk-1", "Updated risk one", probability=4)]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        get_response = self.client.get("/api/risks/")
        self.assertEqual(get_response.status_code, 200)
        records = get_response.json()["riskRegister"]
        records_by_id = {record["id"]: record for record in records}

        self.assertSetEqual(set(records_by_id.keys()), {"risk-1", "risk-2"})
        self.assertEqual(records_by_id["risk-1"]["risk"], "Updated risk one")
        self.assertEqual(records_by_id["risk-1"]["probability"], 4)
        self.assertEqual(records_by_id["risk-2"]["risk"], "Original risk two")

    def test_record_level_update_only_changes_target(self) -> None:
        self.create_risk("risk-1", "Risk one")
        self.create_risk("risk-2", "Risk two")

        update_response = self.client.put(
            "/api/risks/risk-1/",
            data=json.dumps({"risk": {"risk": "Risk one updated", "impact": 5}}),
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["risk"]["id"], "risk-1")

        get_response = self.client.get("/api/risks/")
        records = {record["id"]: record for record in get_response.json()["riskRegister"]}
        self.assertEqual(records["risk-1"]["risk"], "Risk one updated")
        self.assertEqual(records["risk-1"]["impact"], 5)
        self.assertEqual(records["risk-2"]["risk"], "Risk two")

    def test_record_level_update_rejects_path_payload_id_mismatch(self) -> None:
        self.create_risk("risk-1", "Risk one")
        response = self.client.put(
            "/api/risks/risk-1/",
            data=json.dumps({"risk": {"id": "risk-other", "risk": "Mismatch"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Risk id does not match request path.")

    def test_create_sets_created_by_when_payload_includes_actor(self) -> None:
        response = self.client.post(
            "/api/risks/",
            data=json.dumps(
                {
                    "risk": self.risk_payload(
                        "risk-actor",
                        "Actor sourced risk",
                        created_by="risk-user",
                    )
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        created = response.json()["risk"]
        self.assertEqual(created["createdBy"], "risk-user")

    def test_record_level_update_preserves_created_by_when_omitted(self) -> None:
        self.create_risk("risk-1", "Risk one", created_by="risk-user")

        response = self.client.put(
            "/api/risks/risk-1/",
            data=json.dumps({"risk": {"risk": "Risk one updated"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk"]["createdBy"], "risk-user")

    def test_bulk_put_preserves_existing_created_by_when_missing_from_payload(self) -> None:
        self.create_risk("risk-1", "Risk one", created_by="risk-user")

        response = self.client.put(
            "/api/risks/",
            data=json.dumps(
                {
                    "riskRegister": [
                        {
                            "id": "risk-1",
                            "risk": "Risk one updated",
                            "probability": 4,
                            "impact": 4,
                            "date": "2026-01-10",
                            "owner": "Risk Owner",
                        }
                    ]
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        record = next(item for item in response.json()["riskRegister"] if item["id"] == "risk-1")
        self.assertEqual(record["createdBy"], "risk-user")

    def test_bulk_put_accepts_csv_text_to_import_risks(self) -> None:
        csv_payload = (
            "id,risk,probability,impact,date,owner,createdBy\\n"
            ",Imported risk 1,3,4,2026-02-01,Risk Owner,risk-user\\n"
            ",Imported risk 2,2,2,2026-02-02,Risk Owner,\\n"
        )
        response = self.client.put(
            "/api/risks/",
            data=json.dumps({"riskRegister": csv_payload}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        register = response.json()["riskRegister"]
        self.assertEqual(len(register), 2)
        imported_by_name = {item["risk"]: item for item in register}
        self.assertEqual(imported_by_name["Imported risk 1"]["createdBy"], "risk-user")
        self.assertEqual(imported_by_name["Imported risk 2"]["createdBy"], "")

    def test_bulk_put_rejects_csv_missing_required_columns(self) -> None:
        csv_payload = "risk,probability,impact,date\\nMissing owner,2,3,2026-02-01\\n"
        response = self.client.put(
            "/api/risks/",
            data=json.dumps({"riskRegister": csv_payload}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing required columns", response.json()["detail"])

    def test_csv_export_escapes_formula_cells(self) -> None:
        csv_payload = serialize_risk_records_to_csv(
            [
                {
                    "id": "=cmd",
                    "risk": "+sum(A1:A2)",
                    "probability": 3,
                    "impact": 4,
                    "initialRiskLevel": 12,
                    "date": "2026-01-10",
                    "owner": "-owner",
                    "createdBy": "@creator",
                    "closedDate": "",
                    "createdAt": "2026-01-10T00:00:00+00:00",
                    "updatedAt": "2026-01-10T00:00:00+00:00",
                }
            ]
        )

        row = list(csv.DictReader(io.StringIO(csv_payload)))[0]
        self.assertEqual(row["id"], "'=cmd")
        self.assertEqual(row["risk"], "'+sum(A1:A2)")
        self.assertEqual(row["owner"], "'-owner")
        self.assertEqual(row["createdBy"], "'@creator")
