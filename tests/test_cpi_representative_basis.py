"""Regression: CPI headline is YoY; sibling MoM consensus cannot relabel it."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from calendar_market_events import representative_metric, sync_representative_values


def cpi_event():
    return {
        "title": "Consumer Price Index", "country": "US",
        "previous": "0.6%", "consensus": "0.3%", "actual": None,
        "market_metrics": [
            {"key": "cpi_yoy", "label": "CPI YoY", "previous": "3.7%", "consensus": None, "actual": None},
            {"key": "cpi_mom", "label": "CPI MoM", "previous": "0.6%", "consensus": "0.3%", "actual": None},
            {"key": "core_cpi_yoy", "label": "Core CPI YoY", "previous": "2.6%", "consensus": None, "actual": None},
            {"key": "core_cpi_mom", "label": "Core CPI MoM", "previous": "0.3%", "consensus": "0.2%", "actual": None},
        ],
    }


class CpiRepresentativeBasisTests(unittest.TestCase):
    def test_cpi_chooses_headline_yoy_not_mom_forecast(self):
        event = cpi_event()
        self.assertEqual(representative_metric(event)["key"], "cpi_yoy")
        self.assertTrue(sync_representative_values(event))
        self.assertEqual(event["previous"], "3.7%")
        self.assertIsNone(event["consensus"])
        self.assertEqual(event["representative_metric_key"], "cpi_yoy")

    def test_yoy_consensus_remains_yoy_when_published(self):
        event = cpi_event()
        event["market_metrics"][0]["consensus"] = "3.8%"
        sync_representative_values(event)
        self.assertEqual((event["previous"], event["consensus"]), ("3.7%", "3.8%"))

    def test_other_releases_still_prefer_same_measure_with_consensus(self):
        event = cpi_event()
        event["title"] = "Producer Price Index"
        self.assertEqual(representative_metric(event)["key"], "cpi_mom")
        sync_representative_values(event)
        self.assertEqual((event["previous"], event["consensus"]), ("0.6%", "0.3%"))

    def test_missing_yoy_reverts_to_existing_metric_selection(self):
        event = cpi_event()
        event["market_metrics"] = event["market_metrics"][1:]
        self.assertEqual(representative_metric(event)["key"], "cpi_mom")


if __name__ == "__main__":
    unittest.main()
