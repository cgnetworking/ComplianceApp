from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from portal.authorization import PortalAction, PortalResource
from portal.models import PortalState, UploadedPolicy
from portal.policy_download_views import policy_document_download, policy_documents_download_all
from portal.services.policy_downloads import (
    build_all_policies_download,
    build_policy_document_download,
)
from portal.tests.permissions import grant_user_permissions


class PolicyDownloadServiceTests(TestCase):
    def setUp(self) -> None:
        self.uploaded_policy = UploadedPolicy.objects.create(
            document_id="UPL-1",
            title="Uploaded Security Policy",
            document_type="Uploaded policy",
            approver="Pending review",
            review_frequency="Annual",
            path="Portal upload / uploaded-policy.md",
            folder="Uploaded",
            purpose="Uploaded policy purpose.",
            content_html="<h1>Uploaded Policy</h1>",
            raw_text="# Uploaded policy\n\nBody",
            original_filename="uploaded-policy.md",
        )
        PortalState.objects.create(
            key="mapping_state",
            payload={
                "documents": [
                    {
                        "id": "POL-100",
                        "title": "Corporate Security Policy",
                        "type": "Policy",
                        "reviewFrequency": "Annual",
                        "path": "ISMS/policies/corporate-security-policy.md",
                        "contentHtml": "<h1>Corporate Security Policy</h1><p>Mapped content</p>",
                    }
                ],
                "controls": [],
                "activities": [],
                "checklist": [],
                "policyCoverage": [],
            },
        )

    def test_build_policy_document_download_returns_uploaded_policy_raw_text(self) -> None:
        artifact = build_policy_document_download("UPL-1")

        self.assertEqual(artifact.filename, "uploaded-policy.md")
        self.assertEqual(artifact.content, b"# Uploaded policy\n\nBody")
        self.assertEqual(artifact.content_type, "text/markdown; charset=utf-8")

    def test_build_policy_document_download_returns_mapping_html(self) -> None:
        artifact = build_policy_document_download("POL-100")

        self.assertTrue(artifact.filename.endswith(".html"))
        self.assertIn(b"Corporate Security Policy", artifact.content)
        self.assertEqual(artifact.content_type, "text/html; charset=utf-8")

    def test_build_all_policies_download_returns_zip_with_mapping_and_uploaded(self) -> None:
        artifact = build_all_policies_download()

        self.assertEqual(artifact.content_type, "application/zip")
        self.assertTrue(artifact.filename.startswith("policy-library-"))
        self.assertTrue(artifact.filename.endswith(".zip"))

        zip_file = ZipFile(BytesIO(artifact.content), mode="r")
        names = zip_file.namelist()
        self.assertEqual(len(names), 2)
        self.assertTrue(any(name.endswith(".md") for name in names))
        self.assertTrue(any(name.endswith(".html") for name in names))
        self.assertIn(b"# Uploaded policy", b"".join(zip_file.read(name) for name in names))


class PolicyDownloadViewTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="download-user", password="password")
        grant_user_permissions(self.user, (PortalResource.POLICY_DOCUMENT, PortalAction.EXPORT))
        self.factory = RequestFactory()

        UploadedPolicy.objects.create(
            document_id="UPL-2",
            title="Uploaded Download Policy",
            document_type="Uploaded policy",
            approver="Pending review",
            review_frequency="Annual",
            path="Portal upload / download-policy.txt",
            folder="Uploaded",
            purpose="Download policy purpose.",
            content_html="<p>Uploaded download policy</p>",
            raw_text="uploaded text policy",
            original_filename="download-policy.txt",
        )

    def test_policy_document_download_response_sets_attachment_headers(self) -> None:
        request = self.factory.get("/api/policies/UPL-2/download/")
        request.user = self.user

        response = policy_document_download(request, "UPL-2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("download-policy.txt", response["Content-Disposition"])
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(response.content, b"uploaded text policy")

    def test_policy_documents_download_all_response_sets_zip_headers(self) -> None:
        request = self.factory.get("/api/policies/downloads/all/")
        request.user = self.user

        response = policy_documents_download_all(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(".zip", response["Content-Disposition"])
        self.assertEqual(response["Content-Type"], "application/zip")
        zip_file = ZipFile(BytesIO(response.content), mode="r")
        self.assertTrue(zip_file.namelist())
