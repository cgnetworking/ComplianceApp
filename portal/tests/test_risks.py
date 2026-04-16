from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase


class RiskMutationTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="risk-user", password="password")
        self.client.force_login(self.user)

    def risk_payload(self, risk_id: str, risk_text: str, *, probability: int = 3, impact: int = 3) -> dict[str, object]:
        return {
            "id": risk_id,
            "risk": risk_text,
            "probability": probability,
            "impact": impact,
            "date": "2026-01-10",
            "owner": "Risk Owner",
        }

    def create_risk(self, risk_id: str, risk_text: str) -> None:
        response = self.client.post(
            "/api/risks/",
            data=json.dumps({"risk": self.risk_payload(risk_id, risk_text)}),
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

