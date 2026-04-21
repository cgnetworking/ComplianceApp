from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from portal.authorization import PortalAction, PortalResource
from portal.tests.permissions import grant_user_permissions

INVALID_JSON_BODY = b'{"invalid":'


class ApiJsonValidationTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="api-user", password="password")
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
