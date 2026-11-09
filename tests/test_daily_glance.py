import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_daily_glance as glance  # noqa: E402


def series(*values, start=1):
    return [{"date": f"2026-11-{start + i:02d}", "value": v} for i, v in enumerate(values)]


def observatory(**over):
    obs = {
        "us_completed_session_date": "2026-11-06",
        "generated_kst": "2026-11-09T08:48:09+09:00",
        "tripod_latest": {"ok": True, "date": "2026-11-06", "session_date": "2026-11-06",
                          "ndx": 26989.99, "ma250": 27451.44, "drawdown_52w_pct": -13.5614,
                          "vix10": 20.185, "regime": "상승", "target": "QQQ 50% + QLD 50%",
                          "target_changed": False},
        "series": {
            "NASDAQ100": series(27000, 26800, 26700, 26900, 26629.81, 26989.99),
            "KOSPI": series(5400, 5383.8, 5059.69, start=4),
            "NIKKEI225": series(61000, 61077.9, 57434.77, start=4),
            "HANGSENG": series(24700, 24796.98, 24481.86, start=4),
            "SHCOMP": series(3680, 3689.91, 3649.18, start=4),
            "USDKRW": series(1335, 1340.07, 1356.34, start=4),
            "US10Y": series(4.80, 4.837, 4.859, start=4),
            "BTCUSD": [{"date": "2026-11-06", "value": 75746.9}, {"date": "2026-11-07", "value": 75747.6},
                       {"date": "2026-11-08", "value": 1.0, "session_status": "IN_PROGRESS"}],
        },
    }
    obs.update(over)
    return obs


def brief(close, market_date="2026-11-06", status="VERIFIED", official="VERIFIED"):
    return {"report_date_kst": "2026-11-07", "market_date_us": market_date,
            "editorial_contract": {"close_checks": [{"symbol": "NDX", "close": close, "status": status,
                                                     "official_status": official}]}}


class DailyGlance(unittest.TestCase):
    def test_tripod_lines_match_rule_thresholds(self):
        tri = glance.build(observatory())["tripod"]
        self.assertEqual(tri["pod"], "BIPOD")
        peak = 26989.99 / (1 - 0.135614)
        self.assertAlmostEqual(tri["lines"]["tripod_return"], round(peak * 0.91, 2), places=2)
        self.assertAlmostEqual(tri["lines"]["ma250_lower"], round(27451.44 * 0.95, 2), places=2)
        self.assertIn("NOPOD", tri["next_down"])  # VIX10 >= 18 below the lower band

    def test_numbers_come_from_series_and_ignore_in_progress_bars(self):
        g = glance.build(observatory())
        items = {i["key"]: i for grp in g["groups"] for i in grp["items"]}
        self.assertEqual(items["NASDAQ100"]["d1_pct"], 1.35)
        self.assertEqual(items["BTCUSD"]["date"], "2026-11-07")
        self.assertEqual(items["US10Y"]["d1_bp"], 2.2)
        self.assertEqual(items["SP500"]["status"], "MISSING")
        self.assertIn("SP500", g["quality"]["missing"])

    def test_asia_cross_read_separates_aligned_and_divergent_peers(self):
        cross = {c["type"]: c for c in glance.build(observatory())["cross_read"]}
        self.assertIn("닛케이225와 동조", cross["ASIA_CROSS"]["kind"])
        self.assertIn("상대 선방", cross["ASIA_CROSS"]["kind"])
        self.assertIn("다음 KRX 세션", cross["TIME_LAG"]["text"])
        self.assertIn("외국인 이탈형", cross["FX"]["text"])

    def test_brief_mismatch_is_flagged(self):
        bad = glance.build(observatory(), brief(27154.71))["brief_check"]
        self.assertEqual(bad["status"], "MISMATCH")
        ok = glance.build(observatory(), brief(26989.99))["brief_check"]
        self.assertEqual(ok["status"], "MATCH")
        other = glance.build(observatory(), brief(26000, "2026-11-05"))["brief_check"]
        self.assertEqual(other["status"], "NOT_SAME_SESSION")

    def test_unverified_brief_close_is_never_certified(self):
        for status, official in (("CONFLICT", "NOT_VERIFIED"), ("CROSS_CHECKED", "DELAYED"),
                                 ("VERIFIED", "NOT_VERIFIED"), (None, None)):
            check = glance.build(observatory(), brief(26989.99, status=status, official=official))["brief_check"]
            self.assertEqual(check["status"], "UNVERIFIED", (status, official))

    def test_stale_signal_is_isolated_from_current_bar(self):
        stale = dict(observatory()["tripod_latest"], date="2026-11-05", session_date="2026-11-05", ndx=26629.81)
        g = glance.build(observatory(tripod_latest=stale))
        self.assertEqual(g["consistency"]["status"], "CONFLICT")
        self.assertIn("불일치", g["headline"])
        self.assertNotIn("26,630(+1.35%)", g["headline"])
        price_only = dict(observatory()["tripod_latest"], ndx=27154.71)
        self.assertEqual(glance.build(observatory(tripod_latest=price_only))["consistency"]["status"], "CONFLICT")
        self.assertEqual(glance.build(observatory())["consistency"]["status"], "OK")

    def test_workflow_write_token_only_in_publish_job(self):
        wf = (ROOT / ".github/workflows/market-observatory-daily-glance.yml").read_text(encoding="utf-8")
        top = wf.split("jobs:")[0]
        self.assertIn("contents: read", top)
        self.assertNotIn("contents: write", top)
        publish = wf.split("  publish:")[1]
        self.assertIn("contents: write", publish)
        self.assertIn("github.event_name != 'pull_request'", publish)

    def test_refuses_without_signal_and_never_carries_account_data(self):
        with self.assertRaises(ValueError):
            glance.build(observatory(tripod_latest={"ok": False}))
        g = glance.build(observatory())
        self.assertFalse(g["contains_account_data"])
        self.assertTrue(g["no_trade"])

    def test_page_mounts_versioned_runtime_once(self):
        html = (ROOT / "market-observatory/index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count("daily-glance-v1.js?v="), 1)
        js = (ROOT / "market-observatory/daily-glance-v1.js").read_text(encoding="utf-8")
        self.assertIn("JJOONI_DAILY_GLANCE_V1", js)
        self.assertNotIn("innerHTML = g.", js)  # all fields pass through esc()


if __name__ == "__main__":
    unittest.main()
