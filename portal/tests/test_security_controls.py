from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from portal.models import PortalState


class UploadSecurityTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="upload-user", password="password")
        self.client.force_login(self.user)

    @override_settings(POLICY_UPLOAD_MAX_FILE_BYTES=32)
    def test_policy_upload_rejects_files_over_limit(self) -> None:
        upload = SimpleUploadedFile(
            "large-policy.md",
            b"x" * 33,
            content_type="text/markdown",
        )

        response = self.client.post("/api/policies/uploads/", data={"files": [upload]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("upload limit", response.json()["detail"])

    def test_mapping_upload_rejects_binary_payload_for_text_types(self) -> None:
        upload = SimpleUploadedFile(
            "mapping.csv",
            b"id,name\x00\x01",
            content_type="text/csv",
        )

        response = self.client.post("/api/mapping/uploads/", data={"file": upload})
        self.assertEqual(response.status_code, 400)
        self.assertIn("binary data", response.json()["detail"])

    def test_vendor_upload_rejects_unsupported_extension(self) -> None:
        upload = SimpleUploadedFile(
            "payload.exe",
            b"MZ\x00\x02",
            content_type="application/x-msdownload",
        )

        response = self.client.post("/api/vendors/uploads/", data={"files": [upload]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("not a supported vendor upload type", response.json()["detail"])

    @override_settings(UPLOAD_SCANNING_ENABLED=True)
    def test_vendor_upload_rejects_eicar_signature(self) -> None:
        eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        upload = SimpleUploadedFile(
            "vendor-response.txt",
            eicar,
            content_type="text/plain",
        )

        response = self.client.post("/api/vendors/uploads/", data={"files": [upload]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("failed upload scanning", response.json()["detail"])


class LoginThrottleTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="lock-user", password="correct-password")

    @override_settings(
        LOGIN_THROTTLE_MAX_ATTEMPTS=2,
        LOGIN_THROTTLE_WINDOW_SECONDS=300,
        LOGIN_THROTTLE_LOCKOUT_SECONDS=120,
    )
    def test_failed_password_logins_trigger_lockout_and_audit_entries(self) -> None:
        for _ in range(2):
            response = self.client.post(
                "/login/",
                data={
                    "auth_mode": "password",
                    "username": "lock-user",
                    "password": "wrong-password",
                    "next": "/",
                },
            )
            self.assertEqual(response.status_code, 200)

        locked_response = self.client.post(
            "/login/",
            data={
                "auth_mode": "password",
                "username": "lock-user",
                "password": "correct-password",
                "next": "/",
            },
        )
        self.assertEqual(locked_response.status_code, 200)
        self.assertContains(locked_response, "Too many failed sign-in attempts")
        self.assertNotIn("_auth_user_id", self.client.session)

        review_state = PortalState.objects.get(key="review_state").payload
        failed_entries = [entry for entry in review_state.get("auditLog", []) if entry.get("action") == "failed_login"]
        self.assertGreaterEqual(len(failed_entries), 3)
        reasons = {entry.get("metadata", {}).get("reason") for entry in failed_entries}
        self.assertIn("invalid_credentials", reasons)
        self.assertIn("lockout", reasons)
