"""Tests the M365 connector's normalize() against captured real-shape Graph data,
so the mapping and the full engine pipeline are verified without a live tenant.

Run:  python3 -m unittest tests.test_m365
"""

import json
import unittest
from pathlib import Path

from perikrone.connectors.m365 import normalize
from perikrone.engine import assess

_FIXTURE = Path(__file__).parent / "fixtures" / "m365_sample_graph.json"


class TestM365Normalize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        cls.snapshot = normalize(cls.bundle)
        cls.result = assess(cls.snapshot)

    def test_snapshot_shape(self):
        s = self.snapshot
        self.assertEqual(s["source"], "m365")
        self.assertEqual(s["practice_name"], "Northwind Family Health (M365)")
        self.assertEqual(len(s["users"]), 6)
        self.assertIs(s["security_defaults_enabled"], False)

    def test_mfa_mapping(self):
        by_email = {u["email"]: u for u in self.snapshot["users"]}
        # Registered -> True; not in the registered list -> False.
        self.assertTrue(by_email["rminkus@northwindfh.onmicrosoft.com"]["mfa_enabled"])
        self.assertFalse(by_email["anorthcott@northwindfh.onmicrosoft.com"]["mfa_enabled"])

    def test_admin_and_guest_mapping(self):
        by_email = {u["email"]: u for u in self.snapshot["users"]}
        self.assertTrue(by_email["anorthcott@northwindfh.onmicrosoft.com"]["is_admin"])
        self.assertEqual(
            by_email["ap_brightbill#EXT#@northwindfh.onmicrosoft.com"]["account_type"],
            "guest")

    def test_findings_detected(self):
        ids = {f.check_id for f in self.result.findings}
        # The sample is wired to trip these four.
        for expected in ("no-mfa", "stale-accounts", "admin-sprawl",
                         "security-defaults-off"):
            self.assertIn(expected, ids)
        self.assertIn("external-access", ids)

    def test_mfa_unknown_does_not_false_flag(self):
        # When the MFA report is unavailable, nobody is flagged for missing MFA.
        bundle = dict(self.bundle)
        bundle["mfa_registered_ids"] = None
        result = assess(normalize(bundle))
        self.assertNotIn("no-mfa", {f.check_id for f in result.findings})


if __name__ == "__main__":
    unittest.main()
