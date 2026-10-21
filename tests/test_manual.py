"""Tests the shared guided snapshot builder used by both the CLI manual connector
and the in-app guided web form.

Run:  python3 -m unittest tests.test_manual
"""

import unittest

from perikrone.connectors.manual import build_snapshot, usage_to_last_sign_in
from perikrone.engine import assess


class TestGuidedBuilder(unittest.TestCase):
    def test_usage_mapping(self):
        self.assertIsNotNone(usage_to_last_sign_in("recently"))
        self.assertIsNone(usage_to_last_sign_in("never"))
        # "long ago" resolves to a stale timestamp, distinct from "recently".
        self.assertNotEqual(
            usage_to_last_sign_in("old"), usage_to_last_sign_in("recently"))
        # unknown should not false-flag staleness -> treated like recent.
        self.assertEqual(usage_to_last_sign_in("unknown"), usage_to_last_sign_in("r"))

    def test_build_snapshot_and_findings(self):
        snap = build_snapshot("Clinic X", False, None, [
            {"name": "Dr. A", "mfa_enabled": False, "is_admin": True, "guest": False,
             "enabled": True, "last_sign_in": usage_to_last_sign_in("recently")},
            {"name": "Temp", "mfa_enabled": False, "is_admin": False, "guest": False,
             "enabled": True, "last_sign_in": usage_to_last_sign_in("never")},
            {"name": "Vendor", "mfa_enabled": True, "is_admin": False, "guest": True,
             "enabled": True, "last_sign_in": usage_to_last_sign_in("recently")},
        ], source="guided")
        self.assertEqual(snap["source"], "guided")
        self.assertEqual(snap["practice_name"], "Clinic X")
        ids = {f.check_id for f in assess(snap).findings}
        for expected in ("no-mfa", "stale-accounts", "external-access",
                         "security-defaults-off"):
            self.assertIn(expected, ids)

    def test_enabled_unknown_defaults_to_enabled(self):
        snap = build_snapshot("X", None, None, [
            {"name": "A", "enabled": None, "mfa_enabled": True,
             "last_sign_in": usage_to_last_sign_in("recently")}])
        self.assertTrue(snap["users"][0]["enabled"])

    def test_blank_name_gets_placeholder(self):
        snap = build_snapshot("", None, None, [{"name": "", "mfa_enabled": True}])
        self.assertEqual(snap["practice_name"], "My Practice")
        self.assertEqual(snap["users"][0]["display_name"], "Account 1")


if __name__ == "__main__":
    unittest.main()
