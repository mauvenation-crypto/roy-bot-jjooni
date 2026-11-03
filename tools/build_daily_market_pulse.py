#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from observatory_session import expected_completed_session

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "market-observatory" / "data"
OUT = DATA / "daily-market-pulse.json"
KST = ZoneInfo("Asia/Seoul")

PRIMARY_LINKS = {
    "finviz_sp500_map": "https://finviz.com/map?t=sec",
    "finviz_calendar": "https://finviz.com/calendar.ashx",
    "tradingview": "https://kr.tradingview.com/",
    "slickcharts_nasdaq100": "https://www.slickcharts.com/nasdaq100",
    "cnn_fear_greed": "https://edition.cnn.com/markets/fear-and-greed",
}
CNN_API = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


def read_json(path: Path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if fallback is None else fallback


def fetch_text(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; JJOONI-Market-Pulse/1.0)",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def series_fact(obs: dict, key: str, kind: str = "pct") -> dict:
    rows = ((obs.get("series") or {}).get(key) or [])
    if not rows:
        return {"value": None, "market_date": None, "change_pct": None, "change_bp": None}
    last = rows[-1] or {}
    prev = rows[-2] if len(rows) > 1 else {}
    value = last.get("value")
    pvalue = prev.get("value")
    try:
        value = float(value)
    except Exception:
        value = None
    try:
        pvalue = float(pvalue)
    except Exception:
        pvalue = None
    change_pct = None
    change_bp = None
    if value is not None and pvalue not in (None, 0):
        change_pct = (value / pvalue - 1.0) * 100.0
    if kind == "rate" and value is not None and pvalue is not None:
        change_bp = (value - pvalue) * 100.0
        change_pct = None
    return {
        "value": value,
        "market_date": last.get("date"),
        "change_pct": change_pct,
        "change_bp": change_bp,
        "source": "OBSERVATORY_CANONICAL",
    }


def sector_proxy(sec: dict) -> tuple[list, dict]:
    group = next((g for g in (sec.get("groups") or []) if g.get("key") == "classic"), {})
    rows = []
    for r in group.get("rows") or []:
        rows.append({
            "ticker": r.get("ticker"),
            "name": r.get("name"),
            "d1_pct": r.get("ret_1d_pct"),
            "w1_pct": r.get("ret_5d_pct"),
            "m1_pct": r.get("ret_1m_pct"),
            "above_ma20": r.get("above_ma20"),
            "observed_date": r.get("observed_date"),
            "source": r.get("source"),
        })
    sm = sec.get("summary") or {}
    count = sm.get("classic_count") or len(rows)
    above = sm.get("classic_above_ma20")
    ratio = None
    try:
        ratio = float(above) / float(count) if float(count) else None
    except Exception:
        pass
    breadth = {
        "finviz_advancers": None,
        "finviz_decliners": None,
        "finviz_unchanged": None,
        "finviz_breadth_ratio": None,
        "proxy_basis": "S&P500_11_SECTOR_ETF_ABOVE_MA20",
        "proxy_above_ma20": above,
        "proxy_count": count,
        "proxy_ratio": ratio,
        "source_status": "WEB_VERIFICATION_REQUIRED",
        "note": "Finviz constituent breadth is intentionally null until web-verified. The sector MA20 ratio is a labeled proxy only.",
    }
    return rows, breadth


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ").strip()


def slickcharts_concentration() -> dict:
    out = {
        "top10": [],
        "top3_weight_pct": None,
        "top10_weight_pct": None,
        "source": "slickcharts_nasdaq100",
        "status": "DEGRADED",
    }
    try:
        body = fetch_text(PRIMARY_LINKS["slickcharts_nasdaq100"])
        items = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.I | re.S):
            cells = [strip_tags(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.I | re.S)]
            if len(cells) < 3:
                continue
            rank_match = re.search(r"\b(\d{1,3})\b", cells[0])
            pct_match = next((re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*%", c) for c in cells if re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*%", c)), None)
            if not rank_match or not pct_match:
                continue
            rank = int(rank_match.group(1))
            if not 1 <= rank <= 100:
                continue
            ticker = next((c for c in cells[1:4] if re.fullmatch(r"[A-Z.]{1,8}", c)), "")
            name = cells[1] if len(cells) > 1 else ticker
            items.append({"rank": rank, "ticker": ticker, "name": name, "weight_pct": float(pct_match.group(1))})
        dedup = {x["rank"]: x for x in items}
        top10 = [dedup[k] for k in sorted(dedup) if k <= 10]
        if len(top10) == 10:
            out["top10"] = top10
            out["top3_weight_pct"] = round(sum(x["weight_pct"] for x in top10[:3]), 4)
            out["top10_weight_pct"] = round(sum(x["weight_pct"] for x in top10), 4)
            out["status"] = "LIVE"
            out["observed_at_kst"] = datetime.now(KST).isoformat(timespec="seconds")
    except Exception as e:
        out["error"] = type(e).__name__
    return out


def find_score(x):
    if isinstance(x, dict):
        lower = {str(k).lower(): v for k, v in x.items()}
        if "score" in lower:
            try:
                score = float(lower["score"])
                if 0 <= score <= 100:
                    return score, str(lower.get("rating") or lower.get("label") or "")
            except Exception:
                pass
        for v in x.values():
            hit = find_score(v)
            if hit:
                return hit
    if isinstance(x, list):
        for v in x:
            hit = find_score(v)
            if hit:
                return hit
    return None


def fear_greed_label(score):
    if score is None:
        return None
    if score <= 24:
        return "EXTREME_FEAR"
    if score <= 44:
        return "FEAR"
    if score <= 55:
        return "NEUTRAL"
    if score <= 75:
        return "GREED"
    return "EXTREME_GREED"


def cnn_fear_greed() -> dict:
    out = {"score": None, "label": None, "provider_label": None, "source": "cnn_fear_greed", "status": "DEGRADED"}
    try:
        obj = json.loads(fetch_text(CNN_API))
        hit = find_score(obj)
        if hit:
            score, provider_label = hit
            out.update({
                "score": round(score, 2),
                "label": fear_greed_label(score),
                "provider_label": provider_label,
                "status": "LIVE",
            })
    except Exception as e:
        out["error"] = type(e).__name__
    return out


def important_calendar(cal: dict, now: datetime) -> list:
    today = now.date()
    rows = []
    for e in cal.get("events") or []:
        try:
            dt = datetime.fromisoformat(str(e.get("datetime_kst") or ""))
        except Exception:
            continue
        delta = (dt.date() - today).days
        if 0 <= delta <= 1 and int(e.get("importance") or 0) >= 2:
            rows.append({
                "datetime_kst": e.get("datetime_kst"),
                "country": e.get("country"),
                "title": e.get("title"),
                "importance": e.get("importance"),
                "previous": e.get("previous"),
                "consensus": e.get("consensus"),
                "actual": e.get("actual"),
                "source": e.get("source"),
                "source_url": e.get("source_url") or e.get("official_url"),
            })
    return rows[:20]


def derive(raw: dict) -> dict:
    score = 0
    used = []
    ndx = ((raw.get("tradingview_cross_asset") or {}).get("ndx") or {})
    vix = ((raw.get("canonical_context") or {}).get("vix") or {})
    us10 = ((raw.get("tradingview_cross_asset") or {}).get("us10y") or {})
    dxy = ((raw.get("tradingview_cross_asset") or {}).get("dxy") or {})
    breadth = ((raw.get("sp500_breadth") or {}).get("finviz_breadth_ratio"))
    if breadth is None:
        breadth = ((raw.get("sp500_breadth") or {}).get("proxy_ratio"))
        breadth_basis = "SECTOR_MA20_PROXY"
    else:
        breadth_basis = "FINVIZ_CONSTITUENT_BREADTH"
    if ndx.get("change_pct") is not None:
        score += 1 if ndx["change_pct"] > 0 else -1
        used.append("NDX_D1")
    if vix.get("change_pct") is not None:
        score += 1 if vix["change_pct"] < 0 else -1
        used.append("VIX_D1")
    if breadth is not None:
        score += 1 if breadth >= 0.55 else (-1 if breadth <= 0.45 else 0)
        used.append(breadth_basis)
    if us10.get("change_bp") is not None:
        score += -1 if us10["change_bp"] >= 5 else (1 if us10["change_bp"] <= -5 else 0)
        used.append("US10Y_D1")
    risk = "RISK_ON" if score >= 2 else ("RISK_OFF" if score <= -2 else "NEUTRAL")
    breadth_label = "BROAD" if breadth is not None and breadth >= 0.60 else ("NARROW" if breadth is not None and breadth <= 0.40 else "MIXED")
    rate_bp = us10.get("change_bp")
    rates = "HIGH" if rate_bp is not None and rate_bp >= 5 else ("EASING" if rate_bp is not None and rate_bp <= -5 else "STABLE")
    dxy_chg = dxy.get("change_pct")
    usd = "STRENGTHENING" if dxy_chg is not None and dxy_chg >= 0.30 else ("EASING" if dxy_chg is not None and dxy_chg <= -0.30 else "STABLE")
    return {
        "rule_version": "DAILY_MARKET_PULSE_REGIME_V1",
        "risk": risk,
        "breadth": breadth_label,
        "breadth_basis": breadth_basis,
        "rates_pressure": rates,
        "usd_pressure": usd,
        "score": score,
        "inputs_used": used,
        "autobot_direct_trade_trigger": False,
    }


def cached_concentration(previous, now):
    """Reuse optional enrichment only with its original verified capture clock."""
    cached = dict((previous.get('raw') or {}).get('nasdaq100_concentration') or {})
    try:
        captured = datetime.fromisoformat(cached.get('observed_at_kst') or '')
        age = (now - captured).total_seconds()
        if cached.get('status') == 'LIVE' and 0 <= age <= 86400:
            return cached
    except (ValueError, TypeError):
        pass
    return {**cached, 'status': 'STALE_FALLBACK'}


def main(offline=False, *, data_dir=None, out=None):
    data_dir = DATA if data_dir is None else Path(data_dir)
    out = OUT if out is None else Path(out)
    now = datetime.now(KST)
    obs = read_json(data_dir / "observatory.json")
    sec = read_json(data_dir / "sector-etf.json")
    cal = read_json(data_dir / "economic-calendar.json")
    previous = read_json(out, {})
    contract = read_json(data_dir / "morning-brief-contract.json")

    market_date = obs.get("us_completed_session_date")
    if not market_date:
        market_date = series_fact(obs, "SP500").get("market_date")

    # A dated bar is not evidence that the US regular session is completed.
    # This shared clock handles EST/EDT, holidays, early closes and grace.
    expected_session = expected_completed_session(now)
    core_dates = {key: str(((obs.get("series") or {}).get(key) or [{}])[-1].get("date") or "")[:10]
                  for key in ("NASDAQ100", "SP500", "VIX")}
    session_aligned = bool(market_date == expected_session and
                           all(day == expected_session for day in core_dates.values()))
    phase = "FINAL" if session_aligned else "STALE"
    session_gate = {"expected_session": expected_session, "actual_session": market_date,
                    "core_dates": core_dates, "aligned": session_aligned,
                    "clock": "America/New_York 16:00 + 15m grace; DST-aware",
                    "price_crosscheck": "NOT_VERIFIED",
                    "note": "FINAL certifies session alignment, not independent price accuracy"}

    sectors, breadth = sector_proxy(sec)
    cross = {
        "ndx": series_fact(obs, "NASDAQ100"),
        "dxy": series_fact(obs, "DXY"),
        "usdkrw": series_fact(obs, "USDKRW"),
        "us10y": series_fact(obs, "US10Y_OFFICIAL", kind="rate"),
        "preferred_web_source": "tradingview",
        "web_verification_status": "REQUIRED_FOR_MORNING_BRIEF",
    }

    raw = {
        "sp500_breadth": breadth,
        "sector_flow": sectors,
        "tradingview_cross_asset": cross,
        "nasdaq100_concentration": cached_concentration(previous, now) if offline else slickcharts_concentration(),
        "fear_greed": {"score": series_fact(obs, "FEAR_GREED").get("value"), "status": "OBSERVATORY_CANONICAL", "market_date": series_fact(obs, "FEAR_GREED").get("market_date")} if offline else cnn_fear_greed(),
        "calendar": important_calendar(cal, now),
        "canonical_context": {
            "sp500": series_fact(obs, "SP500"),
            "vix": series_fact(obs, "VIX"),
        },
    }
    derived = derive(raw)

    history = list(previous.get("history") or [])
    if market_date:
        history = [x for x in history if x.get("market_date_us") != market_date]
        history.append({
            "market_date_us": market_date,
            "generated_kst": now.isoformat(timespec="seconds"),
            "snapshot_status": phase,
            "ndx": cross["ndx"].get("value"),
            "dxy": cross["dxy"].get("value"),
            "usdkrw": cross["usdkrw"].get("value"),
            "us10y": cross["us10y"].get("value"),
            "sp500": raw["canonical_context"]["sp500"].get("value"),
            "vix": raw["canonical_context"]["vix"].get("value"),
            "breadth_ratio": breadth.get("finviz_breadth_ratio"),
            "breadth_proxy_ratio": breadth.get("proxy_ratio"),
            "top10_weight_pct": raw["nasdaq100_concentration"].get("top10_weight_pct"),
            "fear_greed": raw["fear_greed"].get("score"),
            "risk": derived.get("risk"),
        })
        history = sorted(history, key=lambda x: str(x.get("market_date_us") or ""))[-400:]

    source_status = {
        "finviz_sp500_map": "WEB_VERIFICATION_REQUIRED",
        "finviz_calendar": "OBSERVATORY_CALENDAR_AVAILABLE_WEB_CROSSCHECK_REQUIRED",
        "tradingview": "OBSERVATORY_FALLBACK_WEB_VERIFICATION_REQUIRED",
        "slickcharts_nasdaq100": raw["nasdaq100_concentration"].get("status"),
        "cnn_fear_greed": raw["fear_greed"].get("status"),
    }
    required_values = {
        "ndx": cross["ndx"].get("value") is not None,
        "dxy": cross["dxy"].get("value") is not None,
        "usdkrw": cross["usdkrw"].get("value") is not None,
        "us10y": cross["us10y"].get("value") is not None,
        "market_date_us": bool(market_date),
    }
    quality = "LIVE" if session_aligned and all(required_values.values()) else "PARTIAL"

    result = {
        "schema": "JJOONI_DAILY_MARKET_PULSE_V1",
        "generated_kst": now.isoformat(timespec="seconds"),
        "market_date_us": market_date,
        "snapshot_status": phase,
        "session_gate": session_gate,
        "read_only": True,
        "contains_account_data": False,
        "contract": {
            "schema": contract.get("schema"),
            "path": "./morning-brief-contract.json",
        },
        "raw": raw,
        "derived": derived,
        "history": history,
        "quality": {
            "status": quality,
            "required_values": required_values,
            "source_status": source_status,
            "missing_value_policy": "NULL_NOT_ESTIMATE",
        },
        "sources": {
            key: {"url": url, "status": source_status.get(key), "observed_at_kst": now.isoformat(timespec="seconds")}
            for key, url in PRIMARY_LINKS.items()
        },
        "usage_contract": {
            "pb_ai_usable": True,
            "morning_brief_required_web_verification": True,
            "autobot_direct_trade_trigger": False,
            "rollout_stage": "READ_ONLY",
        },
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DAILY_MARKET_PULSE_BUILD=PASS")
    print("market_date_us=", market_date)
    print("snapshot_status=", phase)
    print("quality=", quality)
    print("source_status=", json.dumps(source_status, ensure_ascii=False))


if __name__ == "__main__":
    main()

