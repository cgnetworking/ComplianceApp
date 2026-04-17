from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cryptography.hazmat.primitives.serialization import pkcs12
from django.test import TestCase, override_settings

from portal.assessment_services import (
    AssessmentValidationError,
    assessment_script_contents,
    delete_zero_trust_profile,
    generate_zero_trust_certificate,
)
from portal.models import ZeroTrustAssessmentRun, ZeroTrustCertificate, ZeroTrustTenantProfile


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
