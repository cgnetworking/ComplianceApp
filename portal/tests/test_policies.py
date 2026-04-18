from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from portal.authorization import PortalAction, PortalResource
from portal.models import PortalState, UploadedPolicy
from portal.tests.permissions import grant_user_permissions


class PolicySanitizationTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="policy-user", password="password")
        grant_user_permissions(
            self.user,
            (PortalResource.POLICY_DOCUMENT, PortalAction.ADD),
            (PortalResource.MAPPING, PortalAction.CHANGE),
        )
        self.client.force_login(self.user)

    def test_uploaded_html_policy_is_sanitized_before_persist(self) -> None:
        html_payload = """
        <h1>Policy</h1>
        <p>Allowed paragraph.</p>
        <script>alert('xss')</script>
        <a href="javascript:alert('xss')" onclick="alert('xss')">Bad link</a>
        <img src="x" onerror="alert('xss')">
        """
        upload = SimpleUploadedFile("security.html", html_payload.encode("utf-8"), content_type="text/html")

        response = self.client.post("/api/policies/uploads/", data={"files": [upload]})
        self.assertEqual(response.status_code, 200)

        created_document = response.json()["documents"][0]
        sanitized_html = created_document["contentHtml"].lower()

        self.assertIn("<h1>policy</h1>", sanitized_html)
        self.assertNotIn("<script", sanitized_html)
        self.assertNotIn("javascript:", sanitized_html)
        self.assertNotIn("onclick=", sanitized_html)
        self.assertNotIn("onerror=", sanitized_html)
        self.assertNotIn("<img", sanitized_html)

        stored_policy = UploadedPolicy.objects.get(document_id=created_document["id"])
        self.assertEqual(stored_policy.content_html, created_document["contentHtml"])

    def test_mapping_state_document_html_is_sanitized(self) -> None:
        mapping_payload = {
            "mapping": {
                "documents": [
                    {
                        "id": "DOC-SEC-1",
                        "title": "Secure Mapping Doc",
                        "contentHtml": "<p>safe</p><script>alert(1)</script><a href='javascript:alert(1)'>x</a>",
                    }
                ],
                "controls": [],
                "activities": [],
                "checklist": [],
                "policyCoverage": [],
            }
        }

        response = self.client.put(
            "/api/state/mapping/",
            data=json.dumps(mapping_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        sanitized_html = response.json()["mapping"]["documents"][0]["contentHtml"].lower()
        self.assertIn("<p>safe</p>", sanitized_html)
        self.assertNotIn("<script", sanitized_html)
        self.assertNotIn("javascript:", sanitized_html)

        saved_state = PortalState.objects.get(key="mapping_state").payload
        persisted_html = saved_state["documents"][0]["contentHtml"].lower()
        self.assertIn("<p>safe</p>", persisted_html)
        self.assertNotIn("<script", persisted_html)
        self.assertNotIn("javascript:", persisted_html)
