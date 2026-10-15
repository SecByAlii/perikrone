"""Tests the Google Workspace connector's normalize() against captured real-shape
Directory API data, so the mapping and the engine pipeline are verified without a
live tenant.

Run:  python3 -m unittest tests.test_google
"""

import json
import unittest
from pathlib import Path

from perikrone.connectors.google_workspace import normalize
from perikrone.engine import assess

_FIXTURE = Path(__file__).parent / "fixtures" / "google_directory_sample.json"


class TestGoogleNormalize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        cls.snapshot = normalize(cls.bundle)
        cls.result = assess(cls.snapshot)

    def test_snapshot_shape(self):
        s = self.snapshot
        self.assertEqual(s["source"], "google")
        self.assertEqual(s["practice_name"], "baysidedental.example (Google Workspace)")
        self.assertEqual(len(s["users"]), 8)
        # Google-inapplicable checks are left unset, not guessed.
        self.assertIsNone(s["security_defaults_enabled"])
        self.assertIsNone(s["legacy_auth_allowed"])

    def test_2sv_admin_and_suspended_mapping(self):
        by_email = {u["email"]: u for u in self.snapshot["users"]}
        self.assertFalse(by_email["dr.okafor@baysidedental.example"]["mfa_enabled"])
        self.assertTrue(by_email["dr.okafor@baysidedental.example"]["is_admin"])
        self.assertTrue(by_email["r.delgado@baysidedental.example"]["mfa_enabled"])
        # suspended -> not enabled
        self.assertFalse(by_email["former.biller@baysidedental.example"]["enabled"])
        # isGuestUser -> guest account type
        self.assertEqual(
            by_email["contractor@external-billing.example"]["account_type"], "guest")

    def test_never_login_becomes_none(self):
        by_email = {u["email"]: u for u in self.snapshot["users"]}
        self.assertIsNone(by_email["temp@baysidedental.example"]["last_sign_in"])

    def test_applicable_findings_detected(self):
        ids = {f.check_id for f in self.result.findings}
        # Guest accounts are mapped (isGuestUser), so external-access applies too.
        for expected in ("no-mfa", "stale-accounts", "admin-sprawl", "external-access"):
            self.assertIn(expected, ids)
        # These have no Google equivalent and must NOT fire.
        self.assertNotIn("security-defaults-off", ids)
        self.assertNotIn("legacy-auth-allowed", ids)


if __name__ == "__main__":
    unittest.main()
