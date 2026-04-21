from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from portal.authorization import PortalAction, PortalResource
from portal.password_validation import AlphanumericPasswordValidator
from portal.tests.permissions import grant_user_permissions


class AuthSettingsTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="auth-settings-user", password="password")
        grant_user_permissions(
            self.user,
            (PortalResource.POLICY_DOCUMENT, PortalAction.VIEW),
            (PortalResource.MAPPING, PortalAction.VIEW),
        )
        self.client.force_login(self.user)

    def test_password_validator_rejects_missing_character_classes(self) -> None:
        validator = AlphanumericPasswordValidator()

        with self.assertRaises(ValidationError):
            validator.validate("alllowercase123")
        with self.assertRaises(ValidationError):
            validator.validate("ALLUPPERCASE123")
        with self.assertRaises(ValidationError):
            validator.validate("NoNumbersHere")

    def test_password_validator_accepts_strong_password(self) -> None:
        validator = AlphanumericPasswordValidator()
        validator.validate("ValidPassword123")

    def test_settings_enable_password_session_and_secret_hardening(self) -> None:
        validator_names = [item["NAME"] for item in settings.AUTH_PASSWORD_VALIDATORS]

        self.assertIn("django.contrib.auth.password_validation.MinimumLengthValidator", validator_names)
        self.assertIn("portal.password_validation.AlphanumericPasswordValidator", validator_names)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertGreaterEqual(len(settings.SECRET_KEY), 50)
        if getattr(settings, "LOGIN_TIMEOUT", None) is not None:
            self.assertEqual(settings.SESSION_COOKIE_AGE, settings.LOGIN_TIMEOUT)
        self.assertEqual(settings.SESSION_SAVE_EVERY_REQUEST, bool(settings.LOGIN_PERSISTENCE))

    def test_frontend_uses_meta_tag_for_csrf_token(self) -> None:
        source = Path(settings.BASE_DIR / "webapp" / "js" / "api.js").read_text(encoding="utf-8")

        self.assertIn('meta[name="portal-csrf-token"]', source)
        self.assertNotIn("document.cookie", source)

    def test_portal_pages_render_csrf_meta_tag(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('meta name="portal-csrf-token"', response.content.decode("utf-8"))
