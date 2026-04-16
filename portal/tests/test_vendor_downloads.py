from __future__ import annotations

import csv
import io
import json

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from portal.models import VendorResponse
from portal.services.vendor_downloads import (
    build_all_vendor_responses_download,
    build_single_vendor_response_download,
)
from portal.vendor_download_views import vendor_response_downloads


class VendorDownloadServiceTests(TestCase):
    def create_vendor_response(
        self,
        *,
        external_id: str,
        vendor_name: str = "Acme Vendor",
        file_name: str = "survey.json",
        extension: str = "json",
        mime_type: str = "application/json",
        raw_text: str = '{"ok": true}',
        summary: str = "Summary",
        status: str = "Imported",
    ) -> VendorResponse:
        return VendorResponse.objects.create(
            external_id=external_id,
            vendor_name=vendor_name,
            file_name=file_name,
            extension=extension,
            mime_type=mime_type,
            file_size=len(raw_text.encode("utf-8")),
            raw_text=raw_text,
            summary=summary,
            status=status,
        )

    def test_single_vendor_download_uses_stored_raw_text(self) -> None:
        response = self.create_vendor_response(
            external_id="vendor-download-1",
            vendor_name="Acme & Co",
            file_name="acme_survey.json",
            extension="json",
            mime_type="application/json",
            raw_text='{"status":"complete"}',
        )

        file_name, content, content_type = build_single_vendor_response_download(response.external_id)

        self.assertTrue(file_name.endswith(".json"))
        self.assertIn("Acme-Co", file_name)
        self.assertEqual(content.decode("utf-8"), '{"status":"complete"}')
        self.assertEqual(content_type, "application/json")

    def test_single_vendor_download_falls_back_to_metadata_when_raw_text_missing(self) -> None:
        response = self.create_vendor_response(
            external_id="vendor-download-2",
            vendor_name="Paper Vendor",
            file_name="questionnaire.pdf",
            extension="pdf",
            mime_type="application/pdf",
            raw_text="",
            status="Metadata only",
        )

        file_name, content, content_type = build_single_vendor_response_download(response.external_id)
        payload = json.loads(content.decode("utf-8"))

        self.assertTrue(file_name.endswith(".json"))
        self.assertEqual(payload["id"], "vendor-download-2")
        self.assertEqual(payload["rawTextAvailable"], False)
        self.assertEqual(content_type, "application/json; charset=utf-8")

    def test_all_vendor_download_builds_csv_export(self) -> None:
        self.create_vendor_response(external_id="vendor-download-3", vendor_name="Vendor One", raw_text="answer,one")
        self.create_vendor_response(external_id="vendor-download-4", vendor_name="Vendor Two", raw_text="answer,two")

        file_name, content, content_type = build_all_vendor_responses_download()

        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
        ids = {row["id"] for row in rows}

        self.assertTrue(file_name.startswith("vendor-survey-responses-"))
        self.assertEqual(content_type, "text/csv; charset=utf-8")
        self.assertSetEqual(ids, {"vendor-download-3", "vendor-download-4"})

    def test_all_vendor_download_escapes_formula_cells(self) -> None:
        self.create_vendor_response(
            external_id="=vendor-download-5",
            vendor_name="+Vendor",
            file_name="-file.csv",
            extension="csv",
            mime_type="text/csv",
            raw_text="@raw",
            summary="=summary",
            status="-status",
        )

        _, content, _ = build_all_vendor_responses_download()
        row = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))[0]
        self.assertEqual(row["id"], "'=vendor-download-5")
        self.assertEqual(row["vendorName"], "'+Vendor")
        self.assertEqual(row["fileName"], "'-file.csv")
        self.assertEqual(row["summary"], "'=summary")
        self.assertEqual(row["rawText"], "'@raw")


class VendorDownloadViewTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="vendor-user", password="password")
        self.factory = RequestFactory()

    def create_vendor_response(self, external_id: str, raw_text: str = '{"ok":true}') -> VendorResponse:
        return VendorResponse.objects.create(
            external_id=external_id,
            vendor_name="View Vendor",
            file_name="view_vendor.json",
            extension="json",
            mime_type="application/json",
            file_size=len(raw_text.encode("utf-8")),
            raw_text=raw_text,
            summary="View summary",
            status="Imported",
        )

    def test_view_returns_single_response_download_with_attachment_headers(self) -> None:
        response_model = self.create_vendor_response("vendor-view-1")
        request = self.factory.get("/api/vendors/downloads/", {"responseId": response_model.external_id})
        request.user = self.user

        response = vendor_response_downloads(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertIn(b'{"ok":true}', response.content)

    def test_view_returns_csv_for_all_scope(self) -> None:
        self.create_vendor_response("vendor-view-2", raw_text="alpha")
        self.create_vendor_response("vendor-view-3", raw_text="beta")
        request = self.factory.get("/api/vendors/downloads/", {"scope": "all"})
        request.user = self.user

        response = vendor_response_downloads(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(b"vendor-view-2", response.content)
        self.assertIn(b"vendor-view-3", response.content)
