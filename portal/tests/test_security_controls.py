from __future__ import annotations

import json

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

    @override_settings(UPLOAD_EICAR_SIGNATURE_CHECK_ENABLED=True)
    def test_vendor_upload_rejects_eicar_signature(self) -> None:
        eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        upload = SimpleUploadedFile(
            "vendor-response.txt",
            eicar,
            content_type="text/plain",
        )

        response = self.client.post("/api/vendors/uploads/", data={"files": [upload]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("EICAR test signature", response.json()["detail"])


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

    @override_settings(
        LOGIN_THROTTLE_MAX_ATTEMPTS=2,
        LOGIN_THROTTLE_WINDOW_SECONDS=300,
        LOGIN_THROTTLE_LOCKOUT_SECONDS=120,
    )
    def test_login_throttle_ignores_spoofed_forwarded_for_when_trusted_proxy_sets_real_ip(self) -> None:
        for spoofed_forwarded_for in ["198.51.100.11", "203.0.113.22"]:
            response = self.client.post(
                "/login/",
                data={
                    "auth_mode": "password",
                    "username": "lock-user",
                    "password": "wrong-password",
                    "next": "/",
                },
                REMOTE_ADDR="127.0.0.1",
                HTTP_X_REAL_IP="198.51.100.77",
                HTTP_X_FORWARDED_FOR=spoofed_forwarded_for,
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
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_REAL_IP="198.51.100.77",
            HTTP_X_FORWARDED_FOR="192.0.2.44",
        )
        self.assertEqual(locked_response.status_code, 200)
        self.assertContains(locked_response, "Too many failed sign-in attempts")

        review_state = PortalState.objects.get(key="review_state").payload
        failed_entries = [entry for entry in review_state.get("auditLog", []) if entry.get("action") == "failed_login"]
        self.assertTrue(failed_entries)
        self.assertTrue(
            all(entry.get("metadata", {}).get("clientIp") == "198.51.100.77" for entry in failed_entries)
        )


class AuditVisibilityTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="staff-user",
            password="password",
            is_staff=True,
        )
        self.user = user_model.objects.create_user(
            username="regular-user",
            password="password",
        )
        self.other_user = user_model.objects.create_user(
            username="other-user",
            password="password",
        )
        PortalState.objects.create(
            key="review_state",
            payload={
                "activities": {"m0::task-1": True},
                "checklist": {"m0::task-1": True},
                "completedAt": {"m0::task-1": "2026-04-15T08:00:00+00:00"},
                "auditLog": [
                    {
                        "id": "audit-failed-login",
                        "action": "failed_login",
                        "entityType": "authentication",
                        "entityId": "regular-user",
                        "summary": "Failed password login for regular-user.",
                        "occurredAt": "2026-04-15T09:30:00+00:00",
                        "actor": {"username": "regular-user", "displayName": "Regular User"},
                        "metadata": {
                            "source": "auth",
                            "reason": "invalid_credentials",
                            "usernameAttempted": "regular-user",
                            "clientIp": "198.51.100.77",
                            "attemptCount": 2,
                            "lockoutRemainingSeconds": 0,
                        },
                    }
                ],
            },
        )

    def test_non_staff_bootstrap_hides_sensitive_audit_data_and_full_user_directory(self) -> None:
        self.client.force_login(self.user)

        review_response = self.client.get("/api/state/?page=reviews")
        self.assertEqual(review_response.status_code, 200)
        review_payload = review_response.json()
        self.assertNotIn("assignableUsers", review_payload)
        self.assertEqual(review_payload["reviewState"]["auditLog"], [])

        risks_response = self.client.get("/api/state/?page=risks")
        self.assertEqual(risks_response.status_code, 200)
        risks_payload = risks_response.json()
        self.assertEqual(
            risks_payload.get("assignableUsers"),
            [{"username": "regular-user", "displayName": "regular-user"}],
        )

    def test_staff_bootstrap_retains_audit_log_and_assignable_users(self) -> None:
        self.client.force_login(self.staff_user)

        response = self.client.get("/api/state/?page=reviews")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["reviewState"]["auditLog"]), 1)
        self.assertGreaterEqual(len(payload.get("assignableUsers", [])), 3)

    def test_non_staff_user_cannot_access_audit_log_page_or_export(self) -> None:
        self.client.force_login(self.user)

        page_response = self.client.get("/audit-log/")
        self.assertEqual(page_response.status_code, 403)

        bootstrap_response = self.client.get("/api/state/?page=audit-log")
        self.assertEqual(bootstrap_response.status_code, 403)

        export_response = self.client.get("/api/audit-log/export.csv")
        self.assertEqual(export_response.status_code, 403)

    def test_non_staff_review_state_save_response_omits_audit_log(self) -> None:
        self.client.force_login(self.user)

        response = self.client.put(
            "/api/state/review/",
            data=json.dumps(
                {
                    "reviewState": {
                        "activities": {"m0::task-2": True},
                        "checklist": {"m0::task-2": True},
                        "completedAt": {},
                    }
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reviewState"]["auditLog"], [])

        stored_review_state = PortalState.objects.get(key="review_state").payload
        self.assertGreaterEqual(len(stored_review_state.get("auditLog", [])), 2)
