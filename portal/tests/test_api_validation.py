from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from portal.authorization import PortalAction, PortalResource
from portal.tests.permissions import grant_user_permissions

INVALID_JSON_BODY = b'{"invalid":'


class ApiJsonValidationTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="api-user", password="password")
        self.other_user = user_model.objects.create_user(username="other-user", password="password")
        self.staff_user = user_model.objects.create_user(
            username="api-staff",
            password="password",
            is_staff=True,
        )
        grant_user_permissions(
            self.user,
            (PortalResource.RISK_RECORD, PortalAction.ADD),
            (PortalResource.RISK_RECORD, PortalAction.CHANGE),
            (PortalResource.REVIEW_STATE, PortalAction.CHANGE),
            (PortalResource.CONTROL_STATE, PortalAction.CHANGE),
            (PortalResource.MAPPING, PortalAction.CHANGE),
        )

    def assert_invalid_json_returns_400(self, method: str, path: str, *, as_staff: bool = False) -> None:
        self.client.force_login(self.staff_user if as_staff else self.user)
        response = self.client.generic(
            method=method,
            path=path,
            data=INVALID_JSON_BODY,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid JSON body.")

    def test_core_json_endpoints_return_400_for_invalid_json(self) -> None:
        endpoints = [
            ("POST", "/api/risks/"),
            ("PATCH", "/api/risks/risk-001/"),
            ("POST", "/api/checklist/"),
            ("PUT", "/api/state/review/"),
            ("PUT", "/api/state/control/"),
            ("PUT", "/api/state/mapping/"),
        ]

        for method, path in endpoints:
            with self.subTest(method=method, path=path):
                self.assert_invalid_json_returns_400(method, path)

    def test_assessment_collection_returns_400_for_invalid_json(self) -> None:
        self.assert_invalid_json_returns_400("POST", "/api/assessments/", as_staff=True)

    def test_checklist_create_rejects_unknown_owner(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/checklist/",
            data=json.dumps(
                {
                    "checklistItem": {
                        "category": "Custom",
                        "item": "Quarterly access review",
                        "frequency": "Quarterly",
                        "owner": "missing-user",
                    }
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Checklist item owner must be selected from an active user.")

    def test_checklist_create_rejects_other_active_owner_for_non_staff(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/checklist/",
            data=json.dumps(
                {
                    "checklistItem": {
                        "category": "Custom",
                        "item": "Quarterly access review",
                        "frequency": "Quarterly",
                        "owner": self.other_user.username,
                    }
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Checklist item owner must be selected from an active user.")

    def test_checklist_create_accepts_current_user_owner(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/checklist/",
            data=json.dumps(
                {
                    "checklistItem": {
                        "category": "Custom",
                        "item": "Quarterly access review",
                        "frequency": "Quarterly",
                        "owner": self.user.username,
                    }
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["checklistItem"]["owner"], self.user.username)

    def test_control_state_rejects_unknown_owner(self) -> None:
        self.client.force_login(self.user)
        response = self.client.put(
            "/api/state/control/",
            data=json.dumps(
                {
                    "controlState": {
                        "A.5.1": {
                            "owner": "missing-user",
                        }
                    }
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Control owner must be selected from an active user.")

    def test_control_state_rejects_other_active_owner_for_non_staff(self) -> None:
        self.client.force_login(self.user)
        response = self.client.put(
            "/api/state/control/",
            data=json.dumps(
                {
                    "controlState": {
                        "A.5.1": {
                            "owner": self.other_user.username,
                        }
                    }
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Control owner must be selected from an active user.")

    def test_risk_create_rejects_unknown_owner(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/risks/",
            data=json.dumps(
                {
                    "risk": {
                        "id": "risk-unknown-owner",
                        "risk": "Third-party outage",
                        "probability": 3,
                        "impact": 4,
                        "date": "2026-01-10",
                        "owner": "missing-user",
                        "createdBy": "api-user",
                    }
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Risk owner must be selected from an active user.")

    def test_risk_create_rejects_other_active_owner_for_non_staff(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/risks/",
            data=json.dumps(
                {
                    "risk": {
                        "id": "risk-other-owner",
                        "risk": "Third-party outage",
                        "probability": 3,
                        "impact": 4,
                        "date": "2026-01-10",
                        "owner": self.other_user.username,
                        "createdBy": "api-user",
                    }
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Risk owner must be selected from an active user.")
