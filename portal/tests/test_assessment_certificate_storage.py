from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cryptography.hazmat.primitives.serialization import pkcs12
from django.test import TestCase, override_settings
from django.utils import timezone

from portal.assessment_services import (
    AssessmentValidationError,
    assessment_script_contents,
    claim_next_zero_trust_run,
    create_zero_trust_run,
    delete_zero_trust_profile,
    generate_zero_trust_certificate,
    get_zero_trust_run_detail,
    ingest_assessment_artifacts,
)
from portal.models import ZeroTrustAssessmentRun, ZeroTrustCertificate, ZeroTrustRunStatus, ZeroTrustTenantProfile


class AssessmentCertificateStorageTests(TestCase):
    def write_password_file(self, directory: str, value: str = "test-assessment-password") -> str:
        password_path = Path(directory) / "assessment-pfx-password"
        password_path.write_text(value + "\n", encoding="utf-8")
        return str(password_path)

    def test_certificate_generation_writes_pfx_to_configured_certificate_root(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-storage",
            display_name="Storage Tenant",
            tenant_id="tenant-storage",
            client_id="client-storage",
        )

        with TemporaryDirectory() as certificate_root, TemporaryDirectory() as secret_root:
            password_file = self.write_password_file(secret_root)
            with override_settings(
                ASSESSMENT_CERTIFICATE_ROOT=certificate_root,
                ASSESSMENT_PFX_PASSWORD_FILE=password_file,
            ):
                payload = generate_zero_trust_certificate(profile.external_id)
                certificate = ZeroTrustCertificate.objects.get(external_id=payload["certificate"]["id"])
                pfx_path = Path(certificate.pfx_path).resolve()
                configured_root = Path(certificate_root).resolve()

                self.assertTrue(pfx_path.is_file())
                self.assertGreater(pfx_path.stat().st_size, 0)
                self.assertEqual(pfx_path.suffix, ".pfx")
                self.assertTrue(str(pfx_path).startswith(str(configured_root)))

                pfx_bytes = pfx_path.read_bytes()
                with self.assertRaises(ValueError):
                    pkcs12.load_key_and_certificates(pfx_bytes, None)
                key, loaded_certificate, _ = pkcs12.load_key_and_certificates(
                    pfx_bytes,
                    b"test-assessment-password",
                )
                self.assertIsNotNone(key)
                self.assertIsNotNone(loaded_certificate)

    def test_profile_delete_removes_certificate_key_file(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-delete",
            display_name="Delete Tenant",
            tenant_id="tenant-delete",
            client_id="client-delete",
        )

        with TemporaryDirectory() as certificate_root, TemporaryDirectory() as secret_root:
            password_file = self.write_password_file(secret_root)
            with override_settings(
                ASSESSMENT_CERTIFICATE_ROOT=certificate_root,
                ASSESSMENT_PFX_PASSWORD_FILE=password_file,
            ):
                payload = generate_zero_trust_certificate(profile.external_id)
                certificate = ZeroTrustCertificate.objects.get(external_id=payload["certificate"]["id"])
                pfx_path = Path(certificate.pfx_path).resolve()
                self.assertTrue(pfx_path.exists())

                delete_zero_trust_profile(profile.external_id)

                self.assertFalse(pfx_path.exists())

    def test_profile_delete_allows_queued_assessment_runs(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-delete-queued",
            display_name="Delete Queued Tenant",
            tenant_id="tenant-delete-queued",
            client_id="client-delete-queued",
        )

        with TemporaryDirectory() as certificate_root, TemporaryDirectory() as secret_root:
            password_file = self.write_password_file(secret_root)
            with override_settings(
                ASSESSMENT_CERTIFICATE_ROOT=certificate_root,
                ASSESSMENT_PFX_PASSWORD_FILE=password_file,
            ):
                payload = generate_zero_trust_certificate(profile.external_id)
                certificate = ZeroTrustCertificate.objects.get(external_id=payload["certificate"]["id"])

                ZeroTrustAssessmentRun.objects.create(
                    external_id="zt-run-delete-queued",
                    profile=profile,
                    certificate=certificate,
                    status=ZeroTrustRunStatus.QUEUED,
                    status_message="Queued for background execution.",
                )

                delete_zero_trust_profile(profile.external_id)

        self.assertFalse(ZeroTrustTenantProfile.objects.filter(external_id=profile.external_id).exists())
        self.assertFalse(ZeroTrustAssessmentRun.objects.filter(external_id="zt-run-delete-queued").exists())

    def test_profile_delete_blocks_claimed_assessment_runs(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-delete-claimed",
            display_name="Delete Claimed Tenant",
            tenant_id="tenant-delete-claimed",
            client_id="client-delete-claimed",
        )

        with TemporaryDirectory() as certificate_root, TemporaryDirectory() as secret_root:
            password_file = self.write_password_file(secret_root)
            with override_settings(
                ASSESSMENT_CERTIFICATE_ROOT=certificate_root,
                ASSESSMENT_PFX_PASSWORD_FILE=password_file,
            ):
                payload = generate_zero_trust_certificate(profile.external_id)
                certificate = ZeroTrustCertificate.objects.get(external_id=payload["certificate"]["id"])

                ZeroTrustAssessmentRun.objects.create(
                    external_id="zt-run-delete-claimed",
                    profile=profile,
                    certificate=certificate,
                    status=ZeroTrustRunStatus.CLAIMED,
                    status_message="Claimed by worker worker-1.",
                )

                with self.assertRaisesMessage(
                    AssessmentValidationError,
                    "Stop or finish the active assessment run before deleting this tenant.",
                ):
                    delete_zero_trust_profile(profile.external_id)

    @override_settings(ASSESSMENT_WORKER_POLL_INTERVAL_SECONDS=10)
    def test_get_run_detail_marks_old_unclaimed_queued_run_stale(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-stale-queued",
            display_name="Stale Queued Tenant",
            tenant_id="tenant-stale-queued",
            client_id="client-stale-queued",
        )

        with TemporaryDirectory() as certificate_root, TemporaryDirectory() as secret_root:
            password_file = self.write_password_file(secret_root)
            with override_settings(
                ASSESSMENT_CERTIFICATE_ROOT=certificate_root,
                ASSESSMENT_PFX_PASSWORD_FILE=password_file,
            ):
                generate_zero_trust_certificate(profile.external_id)
                queued_payload = create_zero_trust_run(profile.external_id)
                queued_run_id = str(queued_payload["id"])
                ZeroTrustAssessmentRun.objects.filter(external_id=queued_run_id).update(
                    created_at=timezone.now() - timedelta(seconds=61)
                )

                detail = get_zero_trust_run_detail(queued_run_id)

        self.assertEqual(detail["run"]["status"], ZeroTrustRunStatus.STALE)
        self.assertIn("No assessment worker claimed the queued run.", detail["run"]["statusMessage"])

    @override_settings(ASSESSMENT_WORKER_POLL_INTERVAL_SECONDS=10)
    def test_get_run_detail_keeps_queued_run_when_another_run_is_active(self) -> None:
        profile_queued = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-queued-active-check",
            display_name="Queued Active Check Tenant",
            tenant_id="tenant-queued-active-check",
            client_id="client-queued-active-check",
        )
        profile_running = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-running-active-check",
            display_name="Running Active Check Tenant",
            tenant_id="tenant-running-active-check",
            client_id="client-running-active-check",
        )

        queued_run = ZeroTrustAssessmentRun.objects.create(
            external_id="zt-run-queued-active-check",
            profile=profile_queued,
            status=ZeroTrustRunStatus.QUEUED,
            status_message="Queued for background execution.",
        )
        ZeroTrustAssessmentRun.objects.filter(pk=queued_run.pk).update(
            created_at=timezone.now() - timedelta(seconds=61)
        )
        running_run = ZeroTrustAssessmentRun.objects.create(
            external_id="zt-run-running-active-check",
            profile=profile_running,
            status=ZeroTrustRunStatus.RUNNING,
            status_message="PowerShell assessment is running.",
            started_at=timezone.now(),
            last_heartbeat_at=timezone.now(),
            lease_expires_at=timezone.now() + timedelta(seconds=300),
        )

        detail = get_zero_trust_run_detail(queued_run.external_id)
        queued_run.refresh_from_db()
        running_run.refresh_from_db()

        self.assertEqual(detail["run"]["status"], ZeroTrustRunStatus.QUEUED)
        self.assertEqual(queued_run.status, ZeroTrustRunStatus.QUEUED)
        self.assertEqual(running_run.status, ZeroTrustRunStatus.RUNNING)

    @override_settings(ASSESSMENT_WORKER_POLL_INTERVAL_SECONDS=10)
    def test_create_run_replaces_expired_queued_run(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-requeue",
            display_name="Requeue Tenant",
            tenant_id="tenant-requeue",
            client_id="client-requeue",
        )

        with TemporaryDirectory() as certificate_root, TemporaryDirectory() as secret_root:
            password_file = self.write_password_file(secret_root)
            with override_settings(
                ASSESSMENT_CERTIFICATE_ROOT=certificate_root,
                ASSESSMENT_PFX_PASSWORD_FILE=password_file,
            ):
                generate_zero_trust_certificate(profile.external_id)
                first_payload = create_zero_trust_run(profile.external_id)
                first_run_id = str(first_payload["id"])
                ZeroTrustAssessmentRun.objects.filter(external_id=first_run_id).update(
                    created_at=timezone.now() - timedelta(seconds=61)
                )

                second_payload = create_zero_trust_run(profile.external_id)

        first_run = ZeroTrustAssessmentRun.objects.get(external_id=first_run_id)
        self.assertEqual(first_run.status, ZeroTrustRunStatus.STALE)
        self.assertEqual(second_payload["status"], ZeroTrustRunStatus.QUEUED)
        self.assertNotEqual(second_payload["id"], first_run_id)

    def test_claim_next_run_marks_queued_run_claimed(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-claim",
            display_name="Claim Tenant",
            tenant_id="tenant-claim",
            client_id="client-claim",
        )

        with TemporaryDirectory() as certificate_root, TemporaryDirectory() as secret_root:
            password_file = self.write_password_file(secret_root)
            with override_settings(
                ASSESSMENT_CERTIFICATE_ROOT=certificate_root,
                ASSESSMENT_PFX_PASSWORD_FILE=password_file,
            ):
                generate_zero_trust_certificate(profile.external_id)
                queued_payload = create_zero_trust_run(profile.external_id)
                claimed_run = claim_next_zero_trust_run(worker_id="worker-test")

        assert claimed_run is not None
        self.assertEqual(claimed_run.external_id, queued_payload["id"])
        claimed_run.refresh_from_db()
        self.assertEqual(claimed_run.status, ZeroTrustRunStatus.CLAIMED)
        self.assertEqual(claimed_run.worker_id, "worker-test")

    def test_assessment_script_reads_runtime_password_file_without_embedded_secret(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-script-password",
            display_name="Script Password Tenant",
            tenant_id="tenant-script-password",
            client_id="client-script-password",
        )

        with TemporaryDirectory() as certificate_root, TemporaryDirectory() as secret_root:
            password_file = self.write_password_file(secret_root)
            with override_settings(
                ASSESSMENT_CERTIFICATE_ROOT=certificate_root,
                ASSESSMENT_PFX_PASSWORD_FILE=password_file,
            ):
                payload = generate_zero_trust_certificate(profile.external_id)
                certificate = ZeroTrustCertificate.objects.get(external_id=payload["certificate"]["id"])

            run = ZeroTrustAssessmentRun.objects.create(
                external_id="zt-run-script-password",
                profile=profile,
                certificate=certificate,
            )

            with override_settings(ASSESSMENT_PFX_PASSWORD_FILE=""):
                with patch.dict(
                    os.environ,
                    {"CREDENTIALS_DIRECTORY": "/run/credentials/portal-assessment-worker.service"},
                    clear=False,
                ):
                    script = assessment_script_contents(run, Path(certificate_root) / "output")

        self.assertIn("/run/credentials/portal-assessment-worker.service/assessment-pfx-password", script)
        self.assertIn("[System.IO.File]::ReadAllText($pfxPasswordPath).Trim()", script)
        self.assertIn("The web app and assessment worker may be using different assessment-pfx-password secrets.", script)
        self.assertIn("function Connect-MgGraph {", script)
        self.assertIn("Microsoft.Graph.Authentication\\Connect-MgGraph @connectMgGraphParams", script)
        self.assertIn("if ($PSBoundParameters.ContainsKey('UseDeviceCode') -and $UseDeviceCode.IsPresent)", script)
        self.assertIn("function Connect-AzAccount {", script)
        self.assertIn("Az.Accounts\\Connect-AzAccount @connectAzAccountParams", script)
        self.assertIn("$connectAzAccountParams.ServicePrincipal = $true", script)
        self.assertIn("Connect-ZtAssessment -ClientId", script)
        self.assertIn("-Service 'Graph','Azure' -Force", script)
        self.assertIn("[System.Security.Cryptography.X509Certificates.X509Store]::new('My', [System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser)", script)
        self.assertNotIn("test-assessment-password", script)

    @override_settings(ASSESSMENT_MODULE_VERSION="2.2.0")
    def test_assessment_script_requires_pinned_module_without_runtime_install(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-script-module",
            display_name="Script Module Tenant",
            tenant_id="tenant-script-module",
            client_id="client-script-module",
        )

        with TemporaryDirectory() as certificate_root, TemporaryDirectory() as secret_root:
            password_file = self.write_password_file(secret_root)
            with override_settings(
                ASSESSMENT_CERTIFICATE_ROOT=certificate_root,
                ASSESSMENT_PFX_PASSWORD_FILE=password_file,
            ):
                payload = generate_zero_trust_certificate(profile.external_id)
                certificate = ZeroTrustCertificate.objects.get(external_id=payload["certificate"]["id"])

            run = ZeroTrustAssessmentRun.objects.create(
                external_id="zt-run-script-module",
                profile=profile,
                certificate=certificate,
            )

            script = assessment_script_contents(run, Path(certificate_root) / "output")

        self.assertIn("$requiredModuleVersion = '2.2.0'", script)
        self.assertIn("Import-Module ZeroTrustAssessment -RequiredVersion $requiredModuleVersion -Force", script)
        self.assertIn("Run scripts/local_setup.sh to install the pinned module before starting the worker.", script)
        self.assertNotIn("Install-Module ZeroTrustAssessment", script)
        self.assertNotIn("Install-PSResource -Name ZeroTrustAssessment", script)

    @override_settings(ASSESSMENT_CERTIFICATE_ROOT="")
    def test_certificate_generation_requires_certificate_root_setting(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-missing-root",
            display_name="Missing Root Tenant",
            tenant_id="tenant-missing-root",
            client_id="client-missing-root",
        )

        with self.assertRaises(AssessmentValidationError) as raised:
            generate_zero_trust_certificate(profile.external_id)
        self.assertEqual(str(raised.exception), "ASSESSMENT_CERTIFICATE_ROOT is not configured on the server.")

    @override_settings(ASSESSMENT_CERTIFICATE_ROOT="")
    def test_certificate_generation_requires_pfx_password_credential(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-missing-password",
            display_name="Missing Password Tenant",
            tenant_id="tenant-missing-password",
            client_id="client-missing-password",
        )

        with TemporaryDirectory() as certificate_root:
            with override_settings(
                ASSESSMENT_CERTIFICATE_ROOT=certificate_root,
                ASSESSMENT_PFX_PASSWORD_FILE="",
            ):
                with patch.dict(os.environ, {"CREDENTIALS_DIRECTORY": ""}, clear=False):
                    with self.assertRaises(AssessmentValidationError) as raised:
                        generate_zero_trust_certificate(profile.external_id)
        self.assertEqual(
            str(raised.exception),
            "Assessment PFX password credential 'assessment-pfx-password' is not available to this service.",
        )

    @override_settings(ASSESSMENT_ARTIFACT_MAX_FILE_BYTES=8)
    def test_ingest_assessment_artifacts_rejects_files_over_per_file_limit(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-large-artifact",
            display_name="Large Artifact Tenant",
            tenant_id="tenant-large-artifact",
            client_id="client-large-artifact",
        )
        run = ZeroTrustAssessmentRun.objects.create(
            external_id="zt-run-large-artifact",
            profile=profile,
        )

        with TemporaryDirectory() as export_root:
            export_path = Path(export_root)
            (export_path / "ZeroTrustAssessmentReport.html").write_bytes(b"123456789")

            with self.assertRaises(AssessmentValidationError) as raised:
                ingest_assessment_artifacts(run, export_path)

        self.assertEqual(
            str(raised.exception),
            "Assessment artifact ZeroTrustAssessmentReport.html exceeds the 8 byte(s) per-file limit.",
        )
