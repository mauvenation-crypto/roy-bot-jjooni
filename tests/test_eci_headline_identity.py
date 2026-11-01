"""Prevent wage-only ECI series from masquerading as headline compensation.

FRED official series identities:
  ECIWAG: wages and salaries, private industry workers
  ECIALLCIV: total compensation, all civilian workers (headline)
These are different statistical populations and must not share vintage keys.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_official_macro as macro


class EciHeadlineIdentityTest(unittest.TestCase):
    def test_headline_eci_uses_total_compensation_series(self):
        cfg = macro.US_DEF["US_ECI"]
        self.assertEqual(cfg["series"], "ECIALLCIV")
        self.assertEqual(cfg["institution"], "BLS")
        self.assertEqual(cfg["kind"], "quarterly_index")
        self.assertIn("Total Compensation", cfg["name"])

    def test_new_eci_vintage_is_isolated_from_legacy_wage_index(self):
        cfg = macro.US_DEF["US_ECI"]
        # Synthetic observations: identity checks must not depend on live values.
        rows = [
            {"date": "2026-04-01", "value": 100.0},
            {"date": "2026-07-01", "value": 100.8},
        ]
        metric = macro.metric_payload("US_ECI", cfg, rows, {"events": []})
        self.assertEqual(metric["transport_source"]["series_id"], "ECIALLCIV")
        self.assertEqual(metric["series_identity"], "ECIALLCIV")
        period = "2026-07-01"
        legacy_key = macro.vintage_key({"key": "US_ECI"}, period)
        headline_key = macro.vintage_key(metric, period)
        self.assertEqual(legacy_key, "US_ECI|2026-07-01")
        self.assertEqual(headline_key, "US_ECI|ECIALLCIV|2026-07-01")
        self.assertNotEqual(legacy_key, headline_key)


if __name__ == "__main__":
    unittest.main()
