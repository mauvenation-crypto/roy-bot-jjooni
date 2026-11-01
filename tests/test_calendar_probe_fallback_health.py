"""Fail closed on BLS probes while recognizing a fully verified FRED fallback."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_observatory_freshness import calendar_probe_health

RELEASE = "https://www.bls.gov/news.release/archives/eci_10302026.htm"
CHECKS = [
    {"adapter": "BLS_eci", "title": "Employment Cost Index",
     "url": RELEASE, "result": "HTTP_403"},
    {"adapter": "BLS_eci", "title": "Employment Cost Index",
     "url": RELEASE.replace(".htm", ".pdf"), "result": "HTTP_403"},
    {"adapter": "BLS_eci", "title": "Employment Cost Index",
     "url": "https://www.bls.gov/news.release/history/eci_10302026.txt",
     "result": "HTTP_403"},
]
SUCCESS = {
    "adapter": "ECI_FRED", "title": "Employment Cost Index",
    "result": "VERIFIED_BLS_TABLE1_FRED_MATCH", "bls_url": RELEASE,
    "reference_period": "2026-09", "actual": "0.8%",
}
EVENT = {
    "title": "Employment Cost Index", "actual": "0.8%",
    "verification_status": "VERIFIED_OFFICIAL", "source_tier": "OFFICIAL",
    "official_url": RELEASE,
    "market_metrics": [{"series_id": "ECIALLCIV",
                        "reference_period": "2026-09",
                        "verification_status": "VERIFIED_OFFICIAL"}],
}


class CalendarProbeFallbackHealthTest(unittest.TestCase):
    def test_verified_fallback_resolves_only_same_release(self):
        result = calendar_probe_health(CHECKS + [SUCCESS], [EVENT])
        self.assertEqual(result["state"], "PASS_WITH_TRANSPORT_WARNINGS")
        self.assertEqual(result["failure_count"], 3)
        self.assertEqual(result["unresolved_failure_count"], 0)
        self.assertEqual(result["blocked_releases"], [])
        self.assertEqual(result["transport_blocked_releases"], ["Employment Cost Index"])
        self.assertEqual(result["verified_fallback_releases"], ["Employment Cost Index"])

    def test_bls_transport_blocked_without_verified_fallback(self):
        result = calendar_probe_health(CHECKS, [EVENT])
        self.assertEqual(result["state"], "DEGRADED")
        self.assertEqual(result["unresolved_failure_count"], 3)

    def test_probe_success_without_matching_official_event_fails_closed(self):
        event = dict(EVENT, verification_status="MARKET_REPORTED")
        result = calendar_probe_health(CHECKS + [SUCCESS], [event])
        self.assertEqual(result["state"], "DEGRADED")
        self.assertEqual(result["unresolved_failure_count"], 3)

    def test_wrong_quarter_or_series_fails_closed(self):
        for field, value in [("reference_period", "2026-06"), ("series_id", "ECIWAG")]:
            with self.subTest(field=field):
                event = dict(EVENT, market_metrics=[dict(EVENT["market_metrics"][0], **{field: value})])
                result = calendar_probe_health(CHECKS + [SUCCESS], [event])
                self.assertEqual(result["state"], "DEGRADED")

    def test_different_release_stays_blocked(self):
        other = {"adapter": "BLS_eci", "title": "Employment Cost Index",
                 "url": RELEASE.replace("10302026", "07312026"), "result": "HTTP_403"}
        result = calendar_probe_health(CHECKS + [other, SUCCESS], [EVENT])
        self.assertEqual(result["state"], "DEGRADED")
        self.assertEqual(result["unresolved_failure_count"], 1)
        self.assertEqual(result["failure_count"], 4)

    def test_no_checks_is_not_checked(self):
        self.assertEqual(calendar_probe_health([], [])["state"], "NOT_CHECKED")


if __name__ == "__main__":
    unittest.main()
