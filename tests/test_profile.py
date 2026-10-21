"""Tests the saved-practice-profile store (load/save round-trip)."""

import tempfile
import unittest
from pathlib import Path

from perikrone import profile


class TestProfile(unittest.TestCase):
    def test_missing_profile_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(profile.load_profile(Path(d) / "profile.json"))

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "profile.json"
            data = {"practice_name": "Clinic X", "platform": "google",
                    "accounts": [{"name": "A", "mfa": "no"}]}
            profile.save_profile(data, p)
            got = profile.load_profile(p)
            self.assertEqual(got["platform"], "google")
            self.assertEqual(got["accounts"][0]["name"], "A")

    def test_corrupt_profile_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "profile.json"
            p.write_text("not valid json", encoding="utf-8")
            self.assertIsNone(profile.load_profile(p))


if __name__ == "__main__":
    unittest.main()
