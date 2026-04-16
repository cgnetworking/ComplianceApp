from __future__ import annotations

import hashlib
import io
import json
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from portal.assessment_report_export_views import assessment_reports_export, assessment_run_report_export
from portal.assessment_services import AssessmentValidationError
from portal.models import (
    ZeroTrustAssessmentArtifact,
    ZeroTrustAssessmentRun,
    ZeroTrustRunStatus,
    ZeroTrustTenantProfile,
)
from portal.services.assessment_report_exports import (
    create_assessment_reports_export,
    create_assessment_run_report_export,
)


class AssessmentReportExportTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="assessment-export-staff",
            password="password",
            is_staff=True,
        )
        self.non_staff_user = user_model.objects.create_user(
            username="assessment-export-user",
            password="password",
            is_staff=False,
        )
        self.factory = RequestFactory()

        self.profile_alpha = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-alpha",
            display_name="Alpha Tenant",
            tenant_id="tenant-alpha",
            client_id="client-alpha",
        )
        self.profile_bravo = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-bravo",
            display_name="Bravo Tenant",
            tenant_id="tenant-bravo",
            client_id="client-bravo",
        )

        self.run_alpha = self.create_run_with_report(
            profile=self.profile_alpha,
            run_external_id="zt-run-alpha",
            artifacts={
                "ZeroTrustAssessmentReport.html": b"<html><body>alpha</body></html>",
                "assets/report.css": b"body { font-family: sans-serif; }",
            },
        )
        self.run_bravo = self.create_run_with_report(
            profile=self.profile_bravo,
            run_external_id="zt-run-bravo",
            artifacts={
                "report.html": b"<html><body>bravo</body></html>",
                "data/summary.json": b'{"score": 91}',
            },
        )
        self.run_without_report = ZeroTrustAssessmentRun.objects.create(
            external_id="zt-run-empty",
            profile=self.profile_alpha,
            status=ZeroTrustRunStatus.SUCCEEDED,
            status_message="Completed without report.",
            entrypoint_relative_path="",
        )

    def create_run_with_report(
        self,
        *,
        profile: ZeroTrustTenantProfile,
        run_external_id: str,
        artifacts: dict[str, bytes],
    ) -> ZeroTrustAssessmentRun:
        entrypoint = next(iter(artifacts.keys()))
        run = ZeroTrustAssessmentRun.objects.create(
            external_id=run_external_id,
            profile=profile,
            status=ZeroTrustRunStatus.SUCCEEDED,
            status_message="Assessment completed.",
            entrypoint_relative_path=entrypoint,
            requested_by="assessment-export-staff",
        )
        for relative_path, content in artifacts.items():
            artifact_type = "html" if relative_path.lower().endswith(".html") else "file"
            content_type = "text/html" if relative_path.lower().endswith(".html") else "application/octet-stream"
            ZeroTrustAssessmentArtifact.objects.create(
                run=run,
                relative_path=relative_path,
                artifact_type=artifact_type,
                content_type=content_type,
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                is_entrypoint=relative_path == entrypoint,
                content=content,
            )
        return run

    def test_create_selected_run_export_contains_manifest_and_artifacts(self) -> None:
        file_name, content = create_assessment_run_report_export(self.run_alpha.external_id)

        self.assertEqual(file_name, "assessment-report-zt-run-alpha.zip")
        with ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            self.assertTrue(any(name.endswith("/ZeroTrustAssessmentReport.html") for name in names))
            self.assertTrue(any(name.endswith("/assets/report.css") for name in names))
            manifest_name = next(name for name in names if name.endswith("/manifest.json"))
            manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
            self.assertEqual(manifest["runId"], self.run_alpha.external_id)
            self.assertEqual(manifest["profileId"], self.profile_alpha.external_id)

    def test_create_all_reports_export_includes_every_stored_report(self) -> None:
        file_name, content = create_assessment_reports_export()

        self.assertTrue(file_name.startswith("assessment-reports-"))
        self.assertTrue(file_name.endswith(".zip"))
        with ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            self.assertIn("manifest.json", names)
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["reportCount"], 2)
            self.assertEqual(
                {item["runId"] for item in manifest["reports"]},
                {self.run_alpha.external_id, self.run_bravo.external_id},
            )

    def test_create_selected_export_rejects_run_without_report(self) -> None:
        with self.assertRaises(AssessmentValidationError):
            create_assessment_run_report_export(self.run_without_report.external_id)

    def test_run_export_view_returns_attachment_headers(self) -> None:
        request = self.factory.get(f"/api/assessments/runs/{self.run_alpha.external_id}/export/")
        request.user = self.staff_user

        response = assessment_run_report_export(request, self.run_alpha.external_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_all_reports_export_view_rejects_non_staff_user(self) -> None:
        request = self.factory.get("/api/assessments/reports/export/")
        request.user = self.non_staff_user

        response = assessment_reports_export(request)

        self.assertEqual(response.status_code, 403)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertIn("Only staff users can manage assessments.", payload["detail"])
