from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import path

from portal.authorization import PortalAction, PortalResource
from portal.tests.permissions import grant_user_permissions

NONCE_RE = re.compile(r"script-src 'nonce-([^']+)'")
SCRIPT_SRC_DIRECTIVE_RE = re.compile(r"script-src ([^;]+);")


def untrusted_html_view(request):
    return HttpResponse("<html><body><script src='/static/js/runtime.js'></script></body></html>")


urlpatterns = [
    path("untrusted/", untrusted_html_view, name="untrusted-html"),
]


class NonceCspTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="csp-user", password="password")
        grant_user_permissions(
            self.user,
            (PortalResource.POLICY_DOCUMENT, PortalAction.VIEW),
            (PortalResource.MAPPING, PortalAction.VIEW),
        )
        self.client.force_login(self.user)

    def test_html_pages_use_nonce_based_csp_and_nonce_script_tags(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        csp = response["Content-Security-Policy"]
        match = NONCE_RE.search(csp)
        self.assertIsNotNone(match)
        nonce = match.group(1) if match else ""
        self.assertTrue(nonce)
        self.assertIn("default-src 'none'", csp)
        self.assertNotIn("script-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertIn("'strict-dynamic'", csp)
        script_src_match = SCRIPT_SRC_DIRECTIVE_RE.search(csp)
        self.assertIsNotNone(script_src_match)
        script_sources = script_src_match.group(1).strip() if script_src_match else ""
        self.assertEqual(script_sources, f"'nonce-{nonce}' 'strict-dynamic'")
        self.assertIn("frame-src 'self'", csp)

        html = response.content.decode("utf-8")
        self.assertIn(f'nonce="{nonce}"', html)
        self.assertIsNone(re.search(r"<script(?![^>]*\bnonce=)", html, flags=re.IGNORECASE))

    def test_nonce_changes_between_requests(self) -> None:
        first = self.client.get("/")
        second = self.client.get("/")
        first_nonce = NONCE_RE.search(first["Content-Security-Policy"]).group(1)
        second_nonce = NONCE_RE.search(second["Content-Security-Policy"]).group(1)
        self.assertNotEqual(first_nonce, second_nonce)

    def test_json_api_responses_do_not_receive_html_csp_header(self) -> None:
        response = self.client.get("/api/state/?page=home")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Security-Policy", response)

    @override_settings(ROOT_URLCONF="portal.tests.test_csp")
    def test_untrusted_html_scripts_do_not_get_nonce_injected(self) -> None:
        response = self.client.get("/untrusted/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("<script src='/static/js/runtime.js'></script>", html)
        self.assertNotIn("nonce=", html)
