from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase


class AssessmentSecurityTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="assessment-staff",
            password="password",
            is_staff=True,
        )
        self.non_staff_user = user_model.objects.create_user(
            username="assessment-user",
            password="password",
        )

    @patch("portal.assessment_views.get_zero_trust_report_html", return_value="<html><body>Report</body></html>")
    def test_report_response_sets_hardened_security_headers(self, mocked_report_html) -> None:
        self.client.force_login(self.staff_user)
        response = self.client.get("/assessments/runs/run-001/report/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])
        self.assertIn("sandbox allow-scripts", response["Content-Security-Policy"])
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        mocked_report_html.assert_called_once_with("run-001")

    @patch(
        "portal.assessment_views.get_zero_trust_artifact",
        return_value=SimpleNamespace(content=b"<html><body>Artifact</body></html>", content_type="text/html"),
    )
    def test_html_artifact_response_applies_report_headers(self, mocked_artifact) -> None:
        self.client.force_login(self.staff_user)
        response = self.client.get("/assessments/runs/run-001/files/report.html")

        self.assertEqual(response.status_code, 200)
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        mocked_artifact.assert_called_once_with("run-001", relative_path="report.html")

    @patch(
        "portal.assessment_views.get_zero_trust_artifact",
        return_value=SimpleNamespace(content=b"{}", content_type="application/json"),
    )
    def test_non_html_artifact_response_sets_nosniff_and_referrer_policy(self, mocked_artifact) -> None:
        self.client.force_login(self.staff_user)
        response = self.client.get("/assessments/runs/run-001/files/summary.json")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Security-Policy", response)
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        mocked_artifact.assert_called_once_with("run-001", relative_path="summary.json")

    def test_non_staff_user_cannot_view_assessment_report(self) -> None:
        self.client.force_login(self.non_staff_user)
        response = self.client.get("/assessments/runs/run-001/report/")
        self.assertEqual(response.status_code, 403)

