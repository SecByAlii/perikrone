"""Tests that the admin-console link follows the practice's platform."""

import json
import unittest
from pathlib import Path

from perikrone.connectors.demo import DemoConnector
from perikrone.connectors.google_workspace import normalize as g_normalize
from perikrone.connectors.manual import build_snapshot
from perikrone.engine import assess
from perikrone.report_html import _console_for, render_html

_GOOGLE_FIXTURE = Path(__file__).parent / "fixtures" / "google_directory_sample.json"


class TestConsoleLinks(unittest.TestCase):
    def test_console_for_each_platform(self):
        self.assertEqual(_console_for("microsoft", None)[1], "https://admin.microsoft.com")
        self.assertEqual(_console_for("google", None)[1], "https://admin.google.com")
        self.assertEqual(
            _console_for("other", "https://admin.clinic.example")[1],
            "https://admin.clinic.example")
        self.assertIsNone(_console_for("other", None))  # no URL -> no button

    def test_other_rejects_unsafe_urls(self):
        # Only absolute https URLs with a host are allowed as custom links.
        self.assertIsNone(_console_for("other", "http://admin.clinic.example"))
        self.assertIsNone(_console_for("other", "javascript:alert(1)"))
        self.assertIsNone(_console_for("other", "/relative/path"))
        self.assertEqual(
            _console_for("other", "https://ok.example")[1], "https://ok.example")

    def test_ehr_console_uses_system_and_https(self):
        c = _console_for("ehr", "https://nextech.example", "Nextech")
        self.assertEqual(c[1], "https://nextech.example")
        self.assertIn("Nextech", c[0])
        # same https safety rule applies to EHR URLs
        self.assertIsNone(_console_for("ehr", "http://nextech.example", "Nextech"))

    def test_ehr_platform_propagates(self):
        snap = build_snapshot("Eye Clinic", None, None,
                              [{"name": "A", "mfa_enabled": False}], source="guided",
                              platform="ehr", admin_url="https:// nextech".replace(" ", ""),
                              ehr_system="Nextech")
        result = assess(snap)
        self.assertEqual(result.platform, "ehr")
        self.assertEqual(result.ehr_system, "Nextech")

    def test_platform_propagates(self):
        self.assertEqual(assess(DemoConnector().collect()).platform, "microsoft")
        google = assess(g_normalize(json.loads(_GOOGLE_FIXTURE.read_text())))
        self.assertEqual(google.platform, "google")

    def test_guided_platform_and_dashboard_link(self):
        snap = build_snapshot("Clinic", False, None,
                              [{"name": "A", "mfa_enabled": False}],
                              source="guided", platform="google")
        result = assess(snap)
        self.assertEqual(result.platform, "google")
        html = render_html(result)
        self.assertIn("admin.google.com", html)
        self.assertNotIn("admin.microsoft.com", html)


if __name__ == "__main__":
    unittest.main()
