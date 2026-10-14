"""Tests the monitoring diff: no-change is quiet, drift degrades, and recovery
is not treated as degradation.

Run:  python3 -m unittest tests.test_monitor
"""

import unittest

from perikrone import monitor
from perikrone.connectors.demo import DemoConnector
from perikrone.engine import assess


class TestMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = DemoConnector().collect()

    def test_no_change_is_quiet(self):
        alerts = monitor.diff_results(assess(self.base), assess(self.base))
        self.assertEqual(alerts, [])
        self.assertFalse(monitor.is_degradation(alerts))

    def test_drift_raises_degradation(self):
        before = assess(self.base)
        after = assess(monitor.apply_demo_drift(self.base))
        alerts = monitor.diff_results(before, after)
        self.assertTrue(monitor.is_degradation(alerts))
        self.assertTrue(any(a.kind in ("new", "worsened") for a in alerts))

    def test_recovery_is_not_degradation(self):
        worse = assess(monitor.apply_demo_drift(self.base))
        better = assess(self.base)
        alerts = monitor.diff_results(worse, better)
        self.assertTrue(alerts)                       # something changed
        self.assertFalse(monitor.is_degradation(alerts))  # ...but it improved
