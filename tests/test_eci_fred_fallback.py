"""Fail-closed tests for the 2026-10-30 BLS ECI headline fallback."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from official_eci_fred_fallback import collect_eci_fred, parse_verified_csv, RELEASES

RELEASE = RELEASES["2026-10-30"]
CSV = ("observation_date,ECIALLCIV\n"
       "2026-04-01,177.178\n"
       "2026-07-01,178.574\n")


def event(**overrides):
    data = {"title": "Employment Cost Index", "country": "US",
            "datetime_kst": "2026-10-30T21:30+09:00",
            "reference_period": ""}
    data.update(overrides)
    return data


class EciFredFallbackTests(unittest.TestCase):
    def test_verified_bls_table1_levels_yield_headline_qoq(self):
        self.assertEqual(parse_verified_csv(CSV, RELEASE), "0.8%")

    def test_wage_or_revised_index_rejected(self):
        with self.assertRaisesRegex(ValueError, "ECI_BLS_TABLE1_FRED_VINTAGE_MISMATCH"):
            parse_verified_csv(CSV.replace("178.574", "178.358"), RELEASE)

    def test_missing_quarter_and_wrong_series_rejected(self):
        with self.assertRaisesRegex(ValueError, "ECI_REFERENCE_QUARTER_MISSING"):
            parse_verified_csv("DATE,ECIALLCIV\n2026-07-01,178.574\n", RELEASE)
        with self.assertRaisesRegex(ValueError, "ECI_SERIES_IDENTITY_MISSING"):
            parse_verified_csv(CSV.replace("ECIALLCIV", "ECIWAG"), RELEASE)

    def test_verified_date_and_period_populate_official_metadata(self):
        e = event()
        checks = []
        with patch("official_eci_fred_fallback.fetch_csv", return_value=CSV):
            result = collect_eci_fred(e, checks)
        self.assertIsNotNone(result)
        rows, url = result
        self.assertIn("ECIALLCIV", url)
        self.assertEqual(rows[0]["actual"], "0.8%")
        self.assertEqual(rows[0]["series_id"], "ECIALLCIV")
        self.assertEqual(rows[0]["value_vintage"], "AS_RELEASED")
        self.assertEqual(rows[0]["official_url"], RELEASE["bls_url"])
        self.assertEqual(e["reference_period"], "September 2026 Employment Cost Index")
        self.assertEqual(checks[-1]["result"], "VERIFIED_BLS_TABLE1_FRED_MATCH")

    def test_release_date_mismatch_fails_closed_without_network(self):
        e = event(datetime_kst="2026-10-29T21:30+09:00")
        with patch("official_eci_fred_fallback.fetch_csv") as fetch:
            self.assertIsNone(collect_eci_fred(e, []))
            fetch.assert_not_called()
        self.assertEqual(e["reference_period"], "")

    def test_existing_conflicting_period_fails_closed(self):
        e = event(reference_period="June 2026 Employment Cost Index")
        with patch("official_eci_fred_fallback.fetch_csv") as fetch:
            self.assertIsNone(collect_eci_fred(e, []))
            fetch.assert_not_called()
        self.assertEqual(e["reference_period"], "June 2026 Employment Cost Index")

    def test_fred_transport_failure_does_not_promote_market_value(self):
        e = event()
        with patch("official_eci_fred_fallback.fetch_csv", side_effect=OSError("403")):
            checks = []
            self.assertIsNone(collect_eci_fred(e, checks))
        self.assertEqual(e["reference_period"], "")
        self.assertEqual(checks[-1]["result"], "OSError")


    def test_end_to_end_calendar_merge_preserves_bls_and_fred_provenance(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from official_calendar_collectors import apply_official_actuals
        e = event(actual="0.8%", source_tier="MARKET_FEED",
                  verification_status="MARKET_REPORTED",
                  market_metrics=[{"key": "eci", "actual": "0.8%",
                                   "source_tier": "MARKET_FEED"}],
                  importance=2)
        calendar = {"events": [e]}
        with patch("official_calendar_collectors.raw_fetch", side_effect=OSError("BLS 403")), \
             patch("official_calendar_collectors.text_fetch", side_effect=OSError("BLS 403")), \
             patch("official_eci_fred_fallback.fetch_csv", return_value=CSV):
            updates, checks = apply_official_actuals(
                calendar, datetime(2026, 11, 1, 23, tzinfo=ZoneInfo("Asia/Seoul")))
        self.assertEqual(updates, 1)
        self.assertEqual(e["source_tier"], "OFFICIAL")
        self.assertEqual(e["verification_status"], "VERIFIED_OFFICIAL")
        self.assertEqual(e["source_url"], __import__("official_eci_fred_fallback").FRED_URL)
        self.assertEqual(e["official_url"], RELEASE["bls_url"])
        self.assertIn("FRED ECIALLCIV", e["market_data_source"])
        self.assertEqual(e["reference_period"], RELEASE["label"])
        self.assertEqual(e["market_metrics"][0]["series_id"], "ECIALLCIV")
        self.assertTrue(any(x.get("result") == "VERIFIED_BLS_TABLE1_FRED_MATCH"
                            for x in checks))

if __name__ == "__main__":
    unittest.main()
