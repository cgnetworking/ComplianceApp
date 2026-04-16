from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings

from portal.assessment_services import (
    AssessmentValidationError,
    delete_zero_trust_profile,
    generate_zero_trust_certificate,
)
from portal.models import ZeroTrustCertificate, ZeroTrustTenantProfile


class AssessmentCertificateStorageTests(TestCase):
    def test_certificate_generation_writes_pfx_to_configured_certificate_root(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-storage",
            display_name="Storage Tenant",
            tenant_id="tenant-storage",
            client_id="client-storage",
        )

        with TemporaryDirectory() as certificate_root:
            with override_settings(ASSESSMENT_CERTIFICATE_ROOT=certificate_root):
                payload = generate_zero_trust_certificate(profile.external_id)
                certificate = ZeroTrustCertificate.objects.get(external_id=payload["certificate"]["id"])
                pfx_path = Path(certificate.pfx_path).resolve()
                configured_root = Path(certificate_root).resolve()

                self.assertTrue(pfx_path.is_file())
                self.assertGreater(pfx_path.stat().st_size, 0)
                self.assertEqual(pfx_path.suffix, ".pfx")
                self.assertTrue(str(pfx_path).startswith(str(configured_root)))

    def test_profile_delete_removes_certificate_key_file(self) -> None:
        profile = ZeroTrustTenantProfile.objects.create(
            external_id="zt-profile-delete",
            display_name="Delete Tenant",
            tenant_id="tenant-delete",
            client_id="client-delete",
        )

        with TemporaryDirectory() as certificate_root:
            with override_settings(ASSESSMENT_CERTIFICATE_ROOT=certificate_root):
                payload = generate_zero_trust_certificate(profile.external_id)
                certificate = ZeroTrustCertificate.objects.get(external_id=payload["certificate"]["id"])
                pfx_path = Path(certificate.pfx_path).resolve()
                self.assertTrue(pfx_path.exists())

                delete_zero_trust_profile(profile.external_id)

                self.assertFalse(pfx_path.exists())

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
