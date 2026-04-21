from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from portal.authorization import PortalAction, PortalResource
from portal.models import PortalState, UploadedPolicy, VendorResponse
from portal.tests.permissions import grant_user_permissions


class PortalObjectPermissionTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.policy_user = user_model.objects.create_user(username="policy-viewer", password="password")
        self.policy_reader = user_model.objects.create_user(username="policy-reader", password="password")
        self.vendor_export_user = user_model.objects.create_user(username="vendor-exporter", password="password")
        self.vendor_raw_user = user_model.objects.create_user(username="vendor-raw", password="password")

        grant_user_permissions(
            self.policy_user,
            (PortalResource.POLICY_DOCUMENT, PortalAction.VIEW),
            (PortalResource.MAPPING, PortalAction.VIEW),
        )
        grant_user_permissions(
            self.vendor_export_user,
            (PortalResource.VENDOR_RESPONSE, PortalAction.EXPORT),
        )
        grant_user_permissions(
            self.vendor_raw_user,
            (PortalResource.VENDOR_RESPONSE, PortalAction.EXPORT),
            (PortalResource.VENDOR_RESPONSE, PortalAction.VIEW_RAW),
        )

        Group.objects.get(name="Policy Reader").user_set.add(self.policy_reader)

        UploadedPolicy.objects.create(
            document_id="UPL-SEC-1",
            title="Uploaded Security Policy",
            document_type="Uploaded policy",
            approver="Pending review",
            review_frequency="Annual",
            path="Portal upload / uploaded-policy.md",
            folder="Uploaded",
            purpose="Uploaded policy purpose.",
            content_html="<h1>Uploaded Policy</h1>",
            raw_text="# Uploaded policy",
            original_filename="uploaded-policy.md",
        )
        PortalState.objects.create(
            key="mapping_state",
            payload={
                "documents": [
                    {
                        "id": "POL-100",
                        "title": "Corporate Security Policy",
                        "contentHtml": "<h1>Policy</h1>",
                    }
                ],
                "controls": [{"id": "A.5.1"}],
                "activities": [{"id": "activity-1"}],
                "checklist": [{"id": "check-1"}],
                "policyCoverage": [{"id": "coverage-1"}],
            },
        )
        PortalState.objects.create(
            key="review_state",
            payload={
                "activities": {"m0::task-1": True},
                "checklist": {"m0::task-1": True},
                "completedAt": {"m0::task-1": "2026-04-15T08:00:00+00:00"},
            },
        )
        VendorResponse.objects.create(
            external_id="vendor-raw-1",
            vendor_name="Example Vendor",
            file_name="vendor.json",
            extension="json",
            mime_type="application/json",
            file_size=18,
            raw_text='{"secret":"raw"}',
            summary="Imported vendor response",
            status="Imported",
        )

    def test_home_bootstrap_only_returns_authorized_sections(self) -> None:
        self.client.force_login(self.policy_user)

        response = self.client.get("/api/state/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("mapping", payload)
        self.assertIn("uploadedDocuments", payload)
        self.assertNotIn("reviewState", payload)
        self.assertNotIn("controlState", payload)
        self.assertNotIn("riskRegister", payload)
        self.assertNotIn("vendorSurveyResponses", payload)

    def test_policy_reader_group_keeps_policy_only_bootstrap_access(self) -> None:
        self.client.force_login(self.policy_reader)

        response = self.client.get("/api/state/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("mapping", payload)
        self.assertIn("uploadedDocuments", payload)
        self.assertNotIn("reviewState", payload)
        self.assertNotIn("controlState", payload)
        self.assertNotIn("riskRegister", payload)
        self.assertNotIn("vendorSurveyResponses", payload)

    def test_vendor_export_hides_raw_text_without_view_raw_permission(self) -> None:
        self.client.force_login(self.vendor_export_user)

        response = self.client.get("/api/vendors/downloads/", {"responseId": "vendor-raw-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json; charset=utf-8")
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["id"], "vendor-raw-1")
        self.assertTrue(payload["rawTextAvailable"])
        self.assertNotIn("rawText", payload)

    def test_vendor_export_with_view_raw_permission_returns_raw_download(self) -> None:
        self.client.force_login(self.vendor_raw_user)

        response = self.client.get("/api/vendors/downloads/", {"responseId": "vendor-raw-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.content, b'{"secret":"raw"}')
