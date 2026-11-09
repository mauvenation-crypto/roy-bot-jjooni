#!/usr/bin/env python3
"""Build the 30-second daily market glance from already-published Observatory data.

Deterministic and offline: every number comes from market-observatory/data/*.json
written by the existing collectors. No web scraping, no LLM, no account data.
The glance also cross-checks the LLM-written morning brief against these numbers
so a provider/post-close value can never silently become the headline again.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "market-observatory" / "data"
OUT = DATA / "daily-glance.json"
KST = ZoneInfo("Asia/Seoul")
SCHEMA = "JJOONI_DAILY_GLANCE_V1"

# Thresholds mirror tools/tripod_rules.py (regime band and target rule).
MA_UP, MA_DOWN, DD_LIMIT, VIX_TRI, VIX_NO = 1.01, 0.95, -9.0, 28.0, 18.0
POD = {"TQQQ 100%": "TRIPOD", "QQQ 50% + QLD 50%": "BIPOD", "현금 100%": "NOPOD"}
BRIEF_TOLERANCE_PCT = 0.10
SIGNAL_PRICE_TOLERANCE_PCT = 0.01

GROUPS = [
    ("미국", [("NASDAQ100", "나스닥100"), ("SP500", "S&P500"), ("NASDAQCOMPOSITE", "나스닥종합"),
             ("DOW", "다우"), ("RUSSELL2000", "러셀2000"), ("VIX", "VIX")]),
    ("아시아", [("KOSPI", "코스피"), ("KOSDAQ", "코스닥"), ("NIKKEI225", "닛케이225"),
               ("HANGSENG", "항셍"), ("SHCOMP", "상하이종합")]),
    ("환율·금리", [("USDKRW", "원/달러"), ("DXY", "달러인덱스"), ("US10Y", "미 10년물"),
                ("US2Y", "미 2년물"), ("KR3Y", "국고 3년")]),
    ("심리·기타", [("FEAR_GREED", "공포탐욕"), ("GOLD", "금"), ("WTI", "WTI"), ("BTCUSD", "비트코인")]),
]
RATE_KEYS = {"US10Y", "US2Y", "KR3Y"}
LEVEL_KEYS = {"FEAR_GREED"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def completed(series):
    return [r for r in series or [] if isinstance(r.get("value"), (int, float))
            and r.get("session_status") != "IN_PROGRESS"]


def pct(a, b):
    return round((a / b - 1) * 100, 2) if a and b else None


def metric(key, label, series):
    rows = completed(series)
    if len(rows) < 2:
        return {"key": key, "label": label, "status": "MISSING"}
    last, prev = rows[-1], rows[-2]
    week = rows[-6] if len(rows) >= 6 else None
    item = {"key": key, "label": label, "date": last["date"], "value": round(last["value"], 4)}
    if key in RATE_KEYS:
        item["d1_bp"] = round((last["value"] - prev["value"]) * 100, 1)
        item["w1_bp"] = round((last["value"] - week["value"]) * 100, 1) if week else None
    elif key in LEVEL_KEYS:
        item["d1_pt"] = round(last["value"] - prev["value"], 1)
    else:
        item["d1_pct"] = pct(last["value"], prev["value"])
        item["w1_pct"] = pct(last["value"], week["value"]) if week else None
    return item


def tripod_block(sig):
    ndx, ma, dd, vix10 = sig["ndx"], sig["ma250"], sig["drawdown_52w_pct"], sig["vix10"]
    peak = ndx / (1 + dd / 100)
    lines = {
        "tripod_return": round(peak * (1 + DD_LIMIT / 100), 2),   # DD back to -9%
        "ma250_upper": round(ma * MA_UP, 2),                      # regime -> 상승
        "ma250_lower": round(ma * MA_DOWN, 2),                    # regime -> 하락
    }
    dist = {k: round((v / ndx - 1) * 100, 2) for k, v in lines.items()}
    pod = POD.get(sig["target"], sig["target"])
    if pod == "BIPOD" and sig["regime"] == "상승":
        if vix10 >= VIX_TRI:
            nxt = f"TRIPOD 복귀는 VIX10 {vix10:.2f}→{VIX_TRI:.0f} 미만과 NDX {lines['tripod_return']:,.0f}(+{dist['tripod_return']:.2f}%) 둘 다 필요"
        else:
            nxt = f"TRIPOD 복귀선 NDX {lines['tripod_return']:,.0f} (+{dist['tripod_return']:.2f}%)"
        down = (f"하락 레짐 전환선 {lines['ma250_lower']:,.0f} ({dist['ma250_lower']:+.2f}%), "
                f"이탈 시 VIX10 {vix10:.2f} {'≥' if vix10 >= VIX_NO else '<'} {VIX_NO:.0f} → "
                f"{'NOPOD' if vix10 >= VIX_NO else 'BIPOD 유지'}")
    elif pod == "TRIPOD":
        nxt = f"DD -9% 이탈선 NDX {lines['tripod_return']:,.0f} ({dist['tripod_return']:+.2f}%) 또는 VIX10 {VIX_TRI:.0f} 이상 시 BIPOD"
        down = f"하락 레짐 전환선 {lines['ma250_lower']:,.0f} ({dist['ma250_lower']:+.2f}%)"
    else:
        nxt = f"상승 레짐 복귀선 NDX {lines['ma250_upper']:,.0f} ({dist['ma250_upper']:+.2f}%)"
        down = f"VIX10 {vix10:.2f}, {VIX_NO:.0f} 미만이면 BIPOD"
    return {
        "session": sig.get("session_date") or sig.get("date"), "pod": pod, "target": sig["target"],
        "regime": sig["regime"], "changed": bool(sig.get("target_changed")),
        "ndx": round(ndx, 2), "ma250": round(ma, 2), "drawdown_52w_pct": round(dd, 2),
        "vix10": round(vix10, 2), "lines": lines, "distance_pct": dist,
        "next_up": nxt, "next_down": down,
    }


def asia_read(by_key, us_session):
    kospi = by_key.get("KOSPI", {})
    peers = [by_key.get(k, {}) for k in ("NIKKEI225", "HANGSENG", "SHCOMP")]
    peers = [p for p in peers if p.get("d1_pct") is not None and p.get("date") == kospi.get("date")]
    out = []
    if kospi.get("d1_pct") is not None and peers:
        avg = round(sum(p["d1_pct"] for p in peers) / len(peers), 2)
        gap = round(kospi["d1_pct"] - avg, 2)
        along = [p for p in peers if abs(p["d1_pct"] - kospi["d1_pct"]) < 1.5]
        apart = [p for p in peers if p not in along]
        if abs(kospi["d1_pct"]) < 1.5 and all(abs(p["d1_pct"]) < 1.5 for p in peers):
            kind = "아시아 전반 평이"
        elif not apart:
            kind = "아시아 공통 움직임"
        elif not along:
            kind = "한국 단독 움직임"
        else:
            kind = (f"{'·'.join(p['label'] for p in along)}와 동조, "
                    f"{'·'.join(p['label'] for p in apart)}는 {'상대 선방' if kospi['d1_pct'] < 0 else '상대 부진'}")
        detail = ", ".join(f"{p['label']} {p['d1_pct']:+.2f}%" for p in peers)
        out.append({"type": "ASIA_CROSS", "kind": kind, "kospi_d1_pct": kospi["d1_pct"],
                    "peer_avg_d1_pct": avg, "gap_pp": gap,
                    "text": f"{kospi['date']} 코스피 {kospi['d1_pct']:+.2f}% vs {detail} → {kind}"})
    if kospi.get("date") and us_session:
        if kospi["date"] <= us_session:
            ndx = by_key.get("NASDAQ100", {})
            out.append({"type": "TIME_LAG", "text":
                        f"한국 최근 종가({kospi['date']})는 미국 {us_session} 장 이전입니다. "
                        f"나스닥100 {ndx.get('d1_pct', 0):+.2f}%는 다음 KRX 세션에 반영됩니다."})
        else:
            out.append({"type": "TIME_LAG", "text":
                        f"한국 최근 종가({kospi['date']})는 미국 {us_session} 장을 이미 반영했습니다."})
    krw = by_key.get("USDKRW", {})
    if krw.get("d1_pct") is not None and kospi.get("d1_pct") is not None:
        if krw["d1_pct"] > 0 and kospi["d1_pct"] < 0:
            read_fx = "원화 약세와 주가 하락이 동시 — 외국인 이탈형"
        elif krw["d1_pct"] < 0 and kospi["d1_pct"] > 0:
            read_fx = "원화 강세와 주가 상승이 동시 — 외국인 유입형"
        else:
            read_fx = "환율과 주가 방향이 엇갈림 — 환율보다 업종 요인"
        out.append({"type": "FX", "text": f"원/달러 {krw['value']:,.1f}원({krw['d1_pct']:+.2f}%) — {read_fx}"})
    return out


def brief_check(brief, by_key, us_session):
    if not brief:
        return {"status": "NO_BRIEF"}
    checks = {c.get("symbol"): c for c in (brief.get("editorial_contract") or {}).get("close_checks", [])}
    ndx = checks.get("NDX")
    result = {"report_date_kst": brief.get("report_date_kst"), "market_date_us": brief.get("market_date_us")}
    if brief.get("market_date_us") != us_session:
        return {**result, "status": "NOT_SAME_SESSION",
                "text": f"아침 시황은 미국 {brief.get('market_date_us')} 기준, 카드는 {us_session} 기준입니다."}
    obs = by_key.get("NASDAQ100", {})
    if not ndx or not isinstance(ndx.get("close"), (int, float)) or obs.get("date") != us_session:
        return {**result, "status": "NOT_COMPARABLE"}
    if ndx.get("status") != "VERIFIED" or ndx.get("official_status") not in (None, "VERIFIED"):
        return {**result, "status": "UNVERIFIED", "brief_status": ndx.get("status"),
                "text": f"아침 시황 NDX 종가가 검증 상태가 아닙니다({ndx.get('status')}). 카드 수치를 기준으로 보세요."}
    diff = round((ndx["close"] / obs["value"] - 1) * 100, 3)
    status = "MATCH" if abs(diff) <= BRIEF_TOLERANCE_PCT else "MISMATCH"
    return {**result, "status": status, "brief_ndx": ndx["close"], "pipeline_ndx": obs["value"], "diff_pct": diff,
            "text": ("아침 시황의 NDX 종가가 파이프라인 확정치와 일치합니다." if status == "MATCH" else
                     f"아침 시황 NDX {ndx['close']:,.2f}가 파이프라인 확정치 {obs['value']:,.2f}와 {diff:+.3f}% 다릅니다. 카드 수치를 우선하세요.")}


def signal_consistency(tri, ndx, us_session):
    """Signal, completed session and NDX bar must describe the same close."""
    reasons = []
    if tri.get("session") != us_session:
        reasons.append(f"signal_session {tri.get('session')} != us_session {us_session}")
    if ndx.get("date") != us_session:
        reasons.append(f"ndx_bar {ndx.get('date')} != us_session {us_session}")
    if ndx.get("value") and abs(tri["ndx"] / ndx["value"] - 1) * 100 > SIGNAL_PRICE_TOLERANCE_PCT:
        reasons.append(f"signal_ndx {tri['ndx']} != bar {ndx['value']}")
    if ndx.get("d1_pct") is None:
        reasons.append("ndx_d1_missing")
    return {"status": "OK" if not reasons else "CONFLICT", "reasons": reasons}


def build(obs, brief=None, now=None):
    now = now or datetime.now(KST)
    sig = obs.get("tripod_latest") or {}
    if sig.get("ok") is not True:
        raise ValueError("TRI-POD signal unavailable")
    us_session = obs.get("us_completed_session_date")
    series = obs.get("series", {})
    groups, by_key = [], {}
    for name, items in GROUPS:
        rows = [metric(k, label, series.get(k)) for k, label in items]
        for r in rows:
            by_key[r["key"]] = r
        groups.append({"name": name, "items": rows})
    tri = tripod_block(sig)
    ndx = by_key.get("NASDAQ100", {})
    consistency = signal_consistency(tri, ndx, us_session)
    if consistency["status"] == "OK":
        headline = (f"{tri['pod']}{' 전환' if tri['changed'] else ' 유지'} · NDX {tri['ndx']:,.0f}"
                    f"({ndx['d1_pct']:+.2f}%) · VIX10 {tri['vix10']:.1f} · DD {tri['drawdown_52w_pct']:.1f}%")
    else:
        headline = (f"⚠️ 신호·시세 불일치 — TRI-POD {tri['pod']}({tri['session']}) 기준, "
                    f"시세 표는 {ndx.get('date', '—')} · 전환선은 참고만")
    missing = [r["key"] for r in by_key.values() if r.get("status") == "MISSING"]
    return {
        "schema": SCHEMA, "generated_kst": now.isoformat(timespec="seconds"),
        "us_session": us_session, "source_generated_kst": obs.get("generated_kst"),
        "read_only": True, "contains_account_data": False, "no_trade": True,
        "headline": headline, "tripod": tri, "consistency": consistency, "groups": groups,
        "cross_read": asia_read(by_key, us_session),
        "brief_check": brief_check(brief, by_key, us_session),
        "quality": {"missing": missing, "number_source": "market-observatory/data/observatory.json only",
                    "note": "카드의 모든 숫자는 저장소 수집 파이프라인 확정치이며 웹 검색·LLM 값을 쓰지 않습니다."},
    }


def main():
    obs = read(DATA / "observatory.json")
    brief_path = DATA / "morning-brief" / "latest.json"
    brief = read(brief_path) if brief_path.exists() else None
    payload = build(obs, brief)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("DAILY_GLANCE", payload["us_session"], payload["headline"], "brief:", payload["brief_check"]["status"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
