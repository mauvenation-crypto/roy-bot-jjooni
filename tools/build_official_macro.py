#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import time
import copy
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from official_macro_releases import collect_releases
from official_macro_registry import KR_SERIES, lookup, series_id, validate_rows

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "market-observatory" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT = DATA_DIR / "official-macro.json"
VINT = DATA_DIR / "official-macro-vintages.json"
CAL = DATA_DIR / "economic-calendar.json"
FEDWATCH = DATA_DIR / "fed-watch.json"
KST = ZoneInfo("Asia/Seoul")
UA = "Mozilla/5.0 JJOONI-Official-Macro/1.0"

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_SOURCE = "Federal Reserve Bank of St. Louis FRED transport"
ECOS_DEADLINE = None


def ecos_request(key, service, *parts):
    remaining = 120 if ECOS_DEADLINE is None else ECOS_DEADLINE - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("ECOS_TOTAL_BUDGET_EXCEEDED")
    # Never log the credential embedded in ECOS URLs.
    print(f"ECOS_REQUEST service={service} page={parts[0]} remaining_sec={remaining:.0f}", flush=True)
    obj = req_json(ecos_url(key, service, *parts), timeout=min(12, remaining))
    if service not in obj:
        code = (obj.get('RESULT') or {}).get('CODE', 'EMPTY_RESPONSE')
        raise RuntimeError(f"ECOS_RESPONSE_ERROR:{code}")
    return obj

US_DEF = {
    "US_CPI": {"series": "CPIAUCSL", "institution": "BLS", "name": "CPI", "group": "inflation", "kind": "monthly_index"},
    "US_CORE_CPI": {"series": "CPILFESL", "institution": "BLS", "name": "Core CPI", "group": "inflation", "kind": "monthly_index"},
    "US_PCE": {"series": "PCEPI", "institution": "BEA", "name": "PCE", "group": "inflation", "kind": "monthly_index", "target": 2.0},
    "US_CORE_PCE": {"series": "PCEPILFE", "institution": "BEA", "name": "Core PCE", "group": "inflation", "kind": "monthly_index", "target": 2.0},
    "US_NFP": {"series": "PAYEMS", "institution": "BLS", "name": "Nonfarm Payrolls", "group": "labor", "kind": "monthly_change", "unit": "K"},
    "US_UNEMPLOYMENT": {"series": "UNRATE", "institution": "BLS", "name": "Unemployment Rate", "group": "labor", "kind": "level", "unit": "%"},
    "US_AHE": {"series": "CES0500000003", "institution": "BLS", "name": "Average Hourly Earnings", "group": "labor", "kind": "monthly_index", "unit": "$/hour"},
    "US_JOLTS": {"series": "JTSJOL", "institution": "BLS", "name": "JOLTS Openings", "group": "labor", "kind": "level", "unit": "K"},
    "US_ECI": {"series": "ECIALLCIV", "institution": "BLS", "name": "Employment Cost Index: Total Compensation (Civilian)", "group": "labor", "kind": "quarterly_index"},
    "US_GDP": {"series": "A191RL1Q225SBEA", "institution": "BEA", "name": "Real GDP", "group": "growth", "kind": "direct", "unit": "% SAAR"},
}

CONSENSUS_ALIASES = {
    "US_CPI": ["cpi", "consumer price index", "headline cpi"],
    "US_CORE_CPI": ["core cpi", "cpi core"],
    "US_PCE": ["pce", "pce price"],
    "US_CORE_PCE": ["core pce", "pce core"],
    "US_NFP": ["nfp", "nonfarm", "non-farm", "payroll"],
    "US_UNEMPLOYMENT": ["unemployment", "실업률"],
    "US_AHE": ["average hourly", "hourly earnings", "임금"],
    "US_JOLTS": ["jolts", "job openings"],
    "US_ECI": ["employment cost", "eci"],
    "US_GDP": ["gdp", "gross domestic product"],
    "US_FED_FUNDS": ["fed rate", "fomc", "federal funds"],
    "KR_CPI": ["소비자물가", "cpi"],
    "KR_GDP": ["gdp", "국내총생산"],
    "KR_BASE_RATE": ["기준금리", "통화정책"],
}

# Consensus must be matched to the exact market measure used by release.actual.
# Never infer across YoY/MoM/QoQ, countries, or unrelated metrics in the same event.
MARKET_METRIC_KEYS = {
    "US_CPI": "cpi_mom",
    "US_CORE_CPI": "core_cpi_mom",
    "US_CORE_PCE": "core_pce_mom",
    "US_NFP": "nfp",
    "US_UNEMPLOYMENT": "unemployment",
    "US_AHE": "avg_hourly_mom",
    "US_JOLTS": "jolts",
    "US_ECI": "eci",
    "US_FED_FUNDS": "fed_rate",
    "KR_CPI": "kr_cpi_yoy",
    "KR_GDP": "gdp_qoq",
}


def market_num(metric_key: str, value):
    x = num(value)
    if x is None:
        return None
    s = str(value or "").strip().upper().replace(",", "")
    if metric_key in {"US_NFP", "US_JOLTS"}:
        if re.search(r"M\s*$", s):
            return x * 1000.0
        if re.search(r"K\s*$", s):
            return x
    return x


def now_kst() -> datetime:
    return datetime.now(KST)


def req_text(url: str, timeout: int = 25) -> str:
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv,application/json,*/*"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.read().decode("utf-8-sig", "replace")


def req_json(url: str, timeout: int = 25):
    return json.loads(req_text(url, timeout=timeout))


def num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(float(v)) else None
    s = str(v).strip().replace(",", "")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        x = float(m.group())
        return x if math.isfinite(x) else None
    except Exception:
        return None


def r4(v):
    return None if v is None else round(float(v), 4)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def fred_series(series_id: str, start: str) -> list[dict]:
    qs = urllib.parse.urlencode({"id": series_id, "cosd": start})
    txt = req_text(FRED_CSV + "?" + qs)
    rows = []
    for row in csv.DictReader(io.StringIO(txt)):
        d = row.get("DATE") or row.get("observation_date") or row.get("date")
        v = row.get(series_id) or row.get("value")
        x = num(v)
        if not d or x is None:
            continue
        rows.append({"date": str(d)[:10], "value": x})
    return rows


def pct(a, b):
    if a is None or b in (None, 0):
        return None
    return (a / b - 1.0) * 100.0


def annualized(a, b, periods_per_year: float):
    if a is None or b in (None, 0):
        return None
    return ((a / b) ** periods_per_year - 1.0) * 100.0


def monthly_index_history(rows: list[dict]) -> list[dict]:
    out = []
    vals = [x["value"] for x in rows]
    for i, row in enumerate(rows):
        v = vals[i]
        out.append({
            "period": row["date"],
            "raw": r4(v),
            "value": r4(pct(v, vals[i - 12])) if i >= 12 else None,
            "yoy": r4(pct(v, vals[i - 12])) if i >= 12 else None,
            "mom": r4(pct(v, vals[i - 1])) if i >= 1 else None,
            "ann_3m": r4(annualized(v, vals[i - 3], 4.0)) if i >= 3 else None,
            "ann_6m": r4(annualized(v, vals[i - 6], 2.0)) if i >= 6 else None,
        })
    return out


def quarterly_index_history(rows: list[dict]) -> list[dict]:
    out = []
    vals = [x["value"] for x in rows]
    for i, row in enumerate(rows):
        v = vals[i]
        out.append({
            "period": row["date"],
            "raw": r4(v),
            "value": r4(pct(v, vals[i - 4])) if i >= 4 else None,
            "yoy": r4(pct(v, vals[i - 4])) if i >= 4 else None,
            "qoq": r4(pct(v, vals[i - 1])) if i >= 1 else None,
        })
    return out


def monthly_change_history(rows: list[dict]) -> list[dict]:
    out = []
    vals = [x["value"] for x in rows]
    for i, row in enumerate(rows):
        ch = vals[i] - vals[i - 1] if i >= 1 else None
        recent3 = [(vals[j] - vals[j - 1]) for j in range(max(1, i - 2), i + 1)]
        recent6 = [(vals[j] - vals[j - 1]) for j in range(max(1, i - 5), i + 1)]
        out.append({
            "period": row["date"],
            "raw": r4(vals[i]),
            "value": r4(ch),
            "avg_3m": r4(sum(recent3) / len(recent3)) if recent3 else None,
            "avg_6m": r4(sum(recent6) / len(recent6)) if recent6 else None,
        })
    return out


def level_history(rows: list[dict]) -> list[dict]:
    out = []
    vals = [x["value"] for x in rows]
    for i, row in enumerate(rows):
        recent3 = vals[max(0, i - 2): i + 1]
        recent6 = vals[max(0, i - 5): i + 1]
        out.append({
            "period": row["date"],
            "raw": r4(vals[i]),
            "value": r4(vals[i]),
            "avg_3m": r4(sum(recent3) / len(recent3)) if recent3 else None,
            "avg_6m": r4(sum(recent6) / len(recent6)) if recent6 else None,
            "yoy_change": r4(vals[i] - vals[i - 12]) if i >= 12 else None,
        })
    return out


def direct_history(rows: list[dict]) -> list[dict]:
    return [{"period": x["date"], "raw": r4(x["value"]), "value": r4(x["value"])} for x in rows]


def metric_history(kind: str, rows: list[dict]) -> list[dict]:
    if kind == "monthly_index":
        return monthly_index_history(rows)
    if kind == "quarterly_index":
        return quarterly_index_history(rows)
    if kind == "monthly_change":
        return monthly_change_history(rows)
    if kind == "monthly_mom":
        hist = monthly_index_history(rows)
        for point in hist:
            point["value"] = point["mom"]
        return hist
    if kind == "level":
        return level_history(rows)
    return direct_history(rows)


def latest_non_null(hist: list[dict], key: str = "value"):
    for x in reversed(hist):
        if x.get(key) is not None:
            return x
    return None


def calendar_consensus(metric_key: str, calendar: dict):
    expected_key = MARKET_METRIC_KEYS.get(metric_key)
    if not expected_key:
        return None
    expected_country = "US" if metric_key.startswith("US_") else ("KR" if metric_key.startswith("KR_") else None)
    cutoff = now_kst().isoformat(timespec="seconds")
    candidates = []
    for e in calendar.get("events", []):
        if expected_country and str(e.get("country") or "").upper() != expected_country:
            continue
        title = str(e.get("title") or "")
        dt = str(e.get("datetime_kst") or e.get("date") or "")
        # Future releases must never supply consensus for the latest already-released official observation.
        if dt and dt > cutoff:
            continue
        for m in e.get("market_metrics", []) or []:
            if str(m.get("key") or "").strip().lower() != expected_key:
                continue
            candidates.append((dt, {
                "previous": m.get("previous"),
                "consensus": m.get("consensus"),
                "calendar_actual": m.get("actual"),
                "event": title,
                "event_kst": dt,
                "market_metric_key": expected_key,
                "source": m.get("source") or e.get("market_data_source") or e.get("source") or "economic-calendar",
            }))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    # A previous month's forecast is not the latest release's consensus.
    return candidates[-1][1]


def release_value(metric_key: str, latest: dict):
    if not latest:
        return None, None
    if metric_key in {"US_CPI", "US_CORE_CPI", "US_PCE", "US_CORE_PCE", "US_AHE"}:
        return latest.get("mom"), "MoM %"
    if metric_key == "US_ECI":
        return latest.get("qoq"), "QoQ %"
    return latest.get("value"), None


def historical_position(hist: list[dict], field: str = "value"):
    xs = [(str(x.get("period") or "")[:10], num(x.get(field))) for x in hist]
    xs = [(d, v) for d, v in xs if d and v is not None]
    if not xs:
        return {"avg_1y": None, "avg_5y": None, "pre_covid_avg": None}
    last = date.fromisoformat(xs[-1][0])
    c1 = (last - timedelta(days=366)).isoformat()
    c5 = (last - timedelta(days=3653 // 2)).isoformat()  # replaced below with exact 5Y
    c5 = (last - timedelta(days=365*5 + 2)).isoformat()
    def avg(rows):
        return r4(sum(v for _, v in rows) / len(rows)) if rows else None
    return {
        "avg_1y": avg([(d, v) for d, v in xs if d >= c1]),
        "avg_5y": avg([(d, v) for d, v in xs if d >= c5]),
        "pre_covid_avg": avg([(d, v) for d, v in xs if "2015-01-01" <= d <= "2019-12-31"]),
        "latest_percentile_10y": r4(100.0 * sum(1 for _, v in xs if v <= xs[-1][1]) / len(xs)),
    }


def metric_payload(metric_key: str, cfg: dict, rows: list[dict], calendar: dict):
    hist = metric_history(cfg["kind"], rows)
    cutoff = (date.today() - timedelta(days=3653 + 400)).isoformat()
    hist = [x for x in hist if x["period"] >= cutoff]
    latest = latest_non_null(hist)
    prev = None
    if latest:
        idx = hist.index(latest)
        for x in reversed(hist[:idx]):
            if x.get("value") is not None:
                prev = x
                break
    rel_actual, rel_measure = release_value(metric_key, latest or {})
    cc = calendar_consensus(metric_key, calendar) or {}
    consensus = market_num(metric_key, cc.get("consensus"))
    surprise = None if rel_actual is None or consensus is None else r4(rel_actual - consensus)
    source_url = f"https://fred.stlouisfed.org/series/{cfg['series']}"
    transport = {
        "provider": FRED_SOURCE,
        "series_id": cfg["series"],
        "url": source_url,
    }
    primary = {
        "institution": cfg["institution"],
        "name": {"BLS": "U.S. Bureau of Labor Statistics", "BEA": "U.S. Bureau of Economic Analysis", "FED": "Federal Reserve"}.get(cfg["institution"], cfg["institution"]),
    }
    out = {
        "key": metric_key,
        "name": cfg["name"],
        "country": "US",
        "group": cfg["group"],
        "frequency": "quarterly" if cfg["kind"] == "quarterly_index" or metric_key == "US_GDP" else "monthly",
        "unit": cfg.get("unit") or ("%" if cfg["kind"] in {"monthly_index", "quarterly_index"} else None),
        "primary_source": primary,
        "transport_source": transport,
        "latest": latest,
        "previous_period": prev,
        "release": {
            "actual": r4(rel_actual),
            "measure": rel_measure or cfg.get("unit"),
            "previous": r4(release_value(metric_key, prev or {})[0]) if prev else None,
            "consensus": r4(consensus),
            "surprise": surprise,
            "consensus_source": {
                "provider": cc.get("source") if cc else None,
                "event": cc.get("event") if cc else None,
                "event_kst": cc.get("event_kst") if cc else None,
                "market_metric_key": cc.get("market_metric_key") if cc else None,
                "contract": "MARKET_CONSENSUS_SEPARATE_FROM_OFFICIAL_ACTUAL",
            },
        },
        "target": cfg.get("target"),
        "historical_position": historical_position(hist),
        "history": hist,
        "status": "LIVE" if latest else "DEGRADED",
    }
    # Preserve historical ECIWAG wage-only vintages under their legacy keys.
    # A new headline ECI source must never be misclassified as a revision.
    if metric_key == "US_ECI":
        out["series_identity"] = cfg["series"]
    return out


def build_us(calendar: dict):
    start = (date.today() - timedelta(days=3653 + 500)).isoformat()
    metrics = {}
    errors = {}
    for key, cfg in US_DEF.items():
        try:
            rows = fred_series(cfg["series"], start)
            if not rows:
                raise RuntimeError("empty series")
            metrics[key] = metric_payload(key, cfg, rows, calendar)
        except Exception as e:
            errors[key] = str(e)
            metrics[key] = {
                "key": key, "name": cfg["name"], "country": "US", "group": cfg["group"],
                "primary_source": {"institution": cfg["institution"]},
                "transport_source": {"provider": FRED_SOURCE, "series_id": cfg["series"]},
                "history": [], "latest": None, "status": "DEGRADED", "error": str(e),
            }

    try:
        lower = fred_series("DFEDTARL", start)
        upper = fred_series("DFEDTARU", start)
        lm = {x["date"]: x["value"] for x in lower}
        um = {x["date"]: x["value"] for x in upper}
        dates = sorted(set(lm) & set(um))
        hist = [{"period": d, "lower": r4(lm[d]), "upper": r4(um[d]), "value": r4((lm[d] + um[d]) / 2.0), "raw": r4((lm[d] + um[d]) / 2.0)} for d in dates]
        latest = latest_non_null(hist)
        cc = calendar_consensus("US_FED_FUNDS", calendar) or {}
        metrics["US_FED_FUNDS"] = {
            "key": "US_FED_FUNDS", "name": "Fed Funds Target Range", "country": "US", "group": "fed",
            "frequency": "FOMC", "unit": "%", "history": hist, "latest": latest,
            "release": {
                "actual": latest.get("value") if latest else None,
                "measure": "target midpoint %",
                "previous": hist[-2].get("value") if len(hist) > 1 else None,
                "consensus": r4(market_num("US_FED_FUNDS", cc.get("consensus"))),
                "surprise": None,
                "consensus_source": {"provider": cc.get("source"), "event": cc.get("event"), "market_metric_key": cc.get("market_metric_key"), "contract": "MARKET_CONSENSUS_SEPARATE_FROM_OFFICIAL_ACTUAL"},
            },
            "primary_source": {"institution": "FED", "name": "Federal Reserve"},
            "transport_source": {"provider": FRED_SOURCE, "series_id": "DFEDTARL / DFEDTARU", "url": "https://fred.stlouisfed.org/series/DFEDTARU"},
            "status": "LIVE" if latest else "DEGRADED",
        }
    except Exception as e:
        errors["US_FED_FUNDS"] = str(e)

    return metrics, errors


def ecos_url(key: str, service: str, *parts) -> str:
    esc = [urllib.parse.quote(str(x), safe="") for x in parts]
    return "https://ecos.bok.or.kr/api/" + service + "/" + key + "/json/kr/" + "/".join(esc)


def ecos_search(key: str, stat: str, cycle: str, start: str, end: str, item1: str, item2: str | None = None):
    metric_key, cfg = lookup(stat, item1, item2)
    old = (load_json(OUT, {}).get('metrics') or {}).get(metric_key, {})
    # Legacy base-rate/headline identities are known; every other series must
    # match its fingerprint before historical observations can be merged.
    if cfg and old.get('series_identity') != series_id(cfg) and metric_key not in ('KR_BASE_RATE', 'KR_CPI'):
        old = {}
    retained = [{'date': p['period'], 'value': p['raw']} for p in old.get('history', [])
                if p.get('period') and p.get('raw') is not None]
    if retained and cycle in ('M', 'Q'):
        # Re-fetch two years for revisions while retaining the earlier series.
        recent = f"{now_kst().year - 2}01" if cycle == 'M' else f"{now_kst().year - 2}Q1"
        start = max(start, recent)
    page_size = 10 if str(key).strip().lower() == "sample" else 1000
    raw_rows = []
    begin = 1
    total = None
    seen = set()
    while total is None or begin <= total:
        if begin > 2000:
            raise RuntimeError('ECOS_PAGE_LIMIT')
        finish = begin + page_size - 1
        parts = [str(begin), str(finish), stat, cycle, start, end, item1]
        if item2:
            parts.append(item2)
        obj = ecos_request(key, "StatisticSearch", *parts)
        block = obj.get("StatisticSearch") or {}
        rows = block.get("row") or []
        signature = json.dumps(rows, sort_keys=True)
        if rows and signature in seen:
            raise RuntimeError('ECOS_REPEATED_PAGE')
        seen.add(signature)
        if total is None:
            try:
                total = int(block.get("list_total_count") or len(rows))
            except Exception:
                total = len(rows)
        if cfg:
            validate_rows(rows, cfg)
        raw_rows.extend(rows)
        if not rows or len(rows) < page_size:
            break
        begin += page_size

    out = []
    for r in raw_rows:
        v = num(r.get("DATA_VALUE"))
        if v is None:
            continue
        t = str(r.get("TIME") or "")
        if cycle == "D" and len(t) == 8:
            p = f"{t[:4]}-{t[4:6]}-{t[6:8]}"
        elif cycle == "M" and len(t) == 6:
            p = f"{t[:4]}-{t[4:6]}-01"
        elif cycle == "Q":
            m = re.match(r"(\d{4})Q([1-4])", t)
            p = f"{m.group(1)}-{(int(m.group(2))-1)*3+1:02d}-01" if m else t
        else:
            p = t
        out.append({"date": p, "value": v})
    if not out:
        raise RuntimeError('ECOS_NO_OBSERVATIONS')
    ded = {x["date"]: x for x in retained + out}
    return [ded[k] for k in sorted(ded)]


def build_kr(calendar: dict):
    global ECOS_DEADLINE
    ECOS_DEADLINE = time.monotonic() + 120
    key = os.getenv("BOK_ECOS_API_KEY", "sample")
    start_m = f"{date.today().year - 11}01"
    end_m = now_kst().strftime("%Y%m")
    start_q = f"{date.today().year - 11}Q1"
    end_q = f"{date.today().year}Q4"
    metrics = {}
    errors = {}

    def make_metric(metric_key, name, group, institution, rows, kind, unit=None, target=None, transport_note=None):
        hist = metric_history(kind, rows)
        latest = latest_non_null(hist)
        prev = None
        if latest:
            i = hist.index(latest)
            prev = latest_non_null(hist[:i])
        cc = calendar_consensus(metric_key, calendar) or {}
        rel_actual = latest.get("value") if latest else None
        consensus = market_num(metric_key, cc.get("consensus"))
        rel_measure = "YoY %" if kind == "monthly_index" else unit
        return {
            "key": metric_key, "name": name, "country": "KR", "group": group,
            "frequency": "quarterly" if metric_key == "KR_GDP" else "monthly",
            "unit": unit, "target": target, "historical_position": historical_position(hist), "history": hist, "latest": latest, "previous_period": prev,
            "release": {
                "actual": r4(rel_actual), "measure": rel_measure,
                "previous": r4(prev.get("value")) if prev else None,
                "consensus": r4(consensus),
                "surprise": None if rel_actual is None or consensus is None else r4(rel_actual - consensus),
                "consensus_source": {"provider": cc.get("source"), "event": cc.get("event"), "contract": "MARKET_CONSENSUS_SEPARATE_FROM_OFFICIAL_ACTUAL"},
            },
            "primary_source": {"institution": institution, "name": {"BOK": "한국은행", "KOSTAT": "통계청"}.get(institution, institution)},
            "transport_source": {"provider": "BOK ECOS official API", "note": transport_note},
            "status": "LIVE" if latest else "DEGRADED",
        }

    for metric_key, cfg in KR_SERIES.items():
        identity = series_id(cfg)
        try:
            quarterly = cfg.get('cycle') == 'Q'
            rows = ecos_search(key, cfg['stat'], cfg.get('cycle', 'M'),
                               start_q if quarterly else start_m, end_q if quarterly else end_m,
                               cfg['item'], cfg.get('item2'))
            metric = make_metric(metric_key, cfg['name'], cfg['group'], cfg['institution'], rows,
                                 cfg['kind'], cfg['unit'], cfg.get('target'))
            metric['series_identity'] = identity
            metric['raw_unit'] = cfg['raw_unit']
            metric['source_tier'] = 'OFFICIAL'
            metric['verification_status'] = 'OFFICIAL_SERIES_IDENTITY_VERIFIED'
            observed = (metric.get('latest') or {}).get('period')
            period = (observed[:4] + 'Q' + str((int(observed[5:7])-1)//3+1)) if observed and quarterly else ((observed or '')[:7].replace('-', ''))
            public_url = ecos_url('sample', 'StatisticSearch', '1', '10', cfg['stat'], cfg.get('cycle', 'M'), period, period, cfg['item'], *([cfg['item2']] if cfg.get('item2') else []))
            metric['source_url'] = public_url
            metric['transport_source'].update(series_id=identity, url=public_url)
            metric['release']['source_url'] = public_url
            metric['release'].update(source_tier='OFFICIAL', checked_kst=now_kst().isoformat(timespec='seconds'),
                                     reference_period=(metric.get('latest') or {}).get('period'))
            metrics[metric_key] = metric
        except Exception as e:
            errors[metric_key] = str(e)
            metrics[metric_key] = make_metric(metric_key, cfg['name'], cfg['group'], cfg['institution'], [], cfg['kind'], cfg['unit'])
            metrics[metric_key].update(error=str(e), series_identity=identity)
    return metrics, errors


def group_regimes(metrics: dict):
    def m(key, field="value"):
        if (metrics.get(key) or {}).get('status') != 'LIVE':
            return None
        x = (metrics.get(key) or {}).get("latest") or {}
        return num(x.get(field))

    us_core_pce_yoy = m("US_CORE_PCE", "yoy")
    us_core_pce_3m = m("US_CORE_PCE", "ann_3m")
    if us_core_pce_yoy is None:
        us_infl = ("GRAY", "DATA_PENDING")
    elif us_core_pce_3m is not None and us_core_pce_3m > us_core_pce_yoy + 0.25:
        us_infl = ("RED", "ACCELERATING")
    elif us_core_pce_yoy > 2.5:
        us_infl = ("ORANGE", "STICKY")
    else:
        us_infl = ("GREEN", "COOLING")

    nfp3, nfp6 = m("US_NFP", "avg_3m"), m("US_NFP", "avg_6m")
    unemp = m("US_UNEMPLOYMENT")
    if nfp3 is None:
        us_labor = ("GRAY", "DATA_PENDING")
    elif nfp6 is not None and nfp3 < nfp6:
        us_labor = ("GREEN", "COOLING")
    elif unemp is not None and unemp < 4.0 and nfp3 > 200:
        us_labor = ("RED", "TIGHT")
    else:
        us_labor = ("ORANGE", "BALANCING")

    gdp = m("US_GDP")
    us_growth = ("GRAY", "DATA_PENDING") if gdp is None else (("GREEN", "EXPANDING") if gdp > 1.0 else (("RED", "CONTRACTING") if gdp < 0 else ("ORANGE", "SLOWING")))
    fed_mid = m("US_FED_FUNDS")
    us_fed = ("GRAY", "DATA_PENDING") if fed_mid is None else (("RED", "RESTRICTIVE") if fed_mid >= 4.0 else (("ORANGE", "MODERATELY_RESTRICTIVE") if fed_mid >= 3.0 else ("GREEN", "EASING")))

    kr_cpi = m("KR_CPI", "yoy")
    kr_cpi3 = m("KR_CPI", "ann_3m")
    if kr_cpi is None:
        kr_infl = ("GRAY", "DATA_PENDING")
    elif kr_cpi3 is not None and kr_cpi3 > kr_cpi + 0.25:
        kr_infl = ("RED", "ACCELERATING")
    elif kr_cpi > 2.5:
        kr_infl = ("ORANGE", "ABOVE_TARGET")
    else:
        kr_infl = ("GREEN", "NEAR_TARGET")

    kr_gdp = m("KR_GDP")
    kr_growth = ("GRAY", "DATA_PENDING") if kr_gdp is None else (("GREEN", "EXPANDING") if kr_gdp > 0 else ("RED", "CONTRACTING"))
    export_live = (metrics.get("KR_EXPORT_YOY") or {}).get("status") == "LIVE"
    semi_live = (metrics.get("KR_SEMICON_EXPORT_YOY") or {}).get("status") == "LIVE"

    def block(pair, why):
        return {"color": pair[0], "regime": pair[1], "why": why}

    return {
        "us": {
            "inflation": block(us_infl, "Core PCE YoY와 최근 3개월 연율 비교"),
            "labor": block(us_labor, "NFP 3개월/6개월 평균과 실업률"),
            "growth": block(us_growth, "실질 GDP 전기비 연율"),
            "fed": block(us_fed, "Fed Funds 목표범위 중간값"),
        },
        "kr": {
            "inflation": block(kr_infl, "CPI YoY와 최근 3개월 연율 비교"),
            "growth": block(kr_growth, "실질 GDP 전기비"),
            "exports": {"color": "GRAY", "regime": "SOURCE_PENDING" if not export_live else "LIVE", "why": "관세청/산업부 공식 수출 시계열"},
            "semiconductor": {"color": "GRAY", "regime": "SOURCE_PENDING" if not semi_live else "LIVE", "why": "관세청/산업부 반도체 수출 시계열"},
        },
    }


def portfolio_context(regimes: dict):
    usi = regimes["us"]["inflation"]["regime"]
    labor = regimes["us"]["labor"]["regime"]
    notes = []
    if usi in {"ACCELERATING", "STICKY"}:
        notes.append({"feature": "US_INFLATION_PRESSURE", "effect": "금리 민감 성장주/레버리지에 부담 요인", "decision_engine": False})
    if usi == "COOLING" and labor in {"COOLING", "BALANCING"}:
        notes.append({"feature": "GOLDILOCKS_SETUP", "effect": "금리 부담 완화 가능성을 점검할 정보 feature", "decision_engine": False})
    notes.append({"feature": "KR_EXPORT_SEMICON", "effect": "공식 수출/반도체 수출이 LIVE가 되면 국내 반도체 익스포저 참고 feature로 사용", "decision_engine": False})
    return notes


def revision_scalar(metric: dict, point: dict):
    key = metric.get("key")
    if key in {"US_CPI", "US_CORE_CPI", "US_PCE", "US_CORE_PCE", "US_AHE", "US_ECI", "KR_CPI", "KR_CORE_CPI"}:
        return point.get("raw")
    return point.get("value")


def vintage_key(metric, period, point=None):
    # Keep old ledger entries intact, but never call a different statistical
    # series or forecast horizon a revision of the preceding identity.
    identity = metric.get('series_identity')
    if metric.get('value_role') == 'official_forecast':
        identity = 'official_forecast:' + str((point or {}).get('forecast_horizon') or metric.get('forecast_horizon'))
    return '|'.join(x for x in (metric['key'], identity, period) if x)


def update_vintages(metrics: dict):
    ledger = load_json(VINT, {"schema": "JJOONI_OFFICIAL_MACRO_VINTAGES_V1", "created_kst": now_kst().isoformat(timespec="seconds"), "vintages": {}})
    vintages = ledger.setdefault("vintages", {})
    detected = now_kst().isoformat(timespec="seconds")
    for key, metric in metrics.items():
        if metric.get('status') != 'LIVE':
            continue
        hist = metric.get("history") or []
        if not hist:
            continue
        for point in hist[-18:]:
            period = str(point.get("period") or "")
            value = revision_scalar(metric, point)
            if not period or value is None:
                continue
            lk = vintage_key(metric, period, point)
            entries = vintages.setdefault(lk, [])
            if not entries:
                entries.append({"version": "baseline_import", "value": r4(value), "captured_kst": detected, "series_identity": metric.get("series_identity"), "source_url": metric.get("source_url") or (metric.get("transport_source") or {}).get("url")})
            elif abs(float(entries[-1]["value"]) - float(value)) > 1e-9:
                rev_no = sum(1 for x in entries if str(x.get("version", "")).startswith("revision_")) + 1
                entries.append({"version": f"revision_{rev_no}", "value": r4(value), "captured_kst": detected, "series_identity": metric.get("series_identity"), "source_url": metric.get("source_url") or (metric.get("transport_source") or {}).get("url")})
        latest = metric.get("latest") or {}
        if latest.get("period"):
            lk = vintage_key(metric, str(latest["period"]), latest)
            metric.setdefault("release", {})["vintage"] = (vintages.get(lk) or [])[-1] if vintages.get(lk) else None
            metric["release"]["vintage_history"] = vintages.get(lk) or []
    ledger["updated_kst"] = detected
    VINT.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ledger


def main():
    calendar = load_json(CAL, {})
    fedwatch = load_json(FEDWATCH, {})
    print('OFFICIAL_MACRO_STAGE=US', flush=True)
    us, us_errors = build_us(calendar)
    print('OFFICIAL_MACRO_STAGE=KR budget_sec=120', flush=True)
    kr, kr_errors = build_kr(calendar)
    metrics = {**us, **kr}
    previous = load_json(OUT, {})
    print('OFFICIAL_MACRO_STAGE=RELEASES', flush=True)
    releases, release_errors = collect_releases(previous)
    for key, metric in releases.items():
        if key == 'KR_EXPORT_YOY' and metrics.get(key, {}).get('latest'):
            ecos = metrics[key]
            # Release publication is primary; ECOS is the historical transport.
            # Preserve raw observations so future incremental ECOS requests can
            # revise them without treating a growth rate as an export amount.
            if metric.get('latest'):
                merged = {p['period']: p for p in ecos.get('history', [])}
                for point in metric['history']:
                    merged[point['period']] = {**merged.get(point['period'], {}), **point}
                metric['history'] = [merged[p] for p in sorted(merged)]
                metric['latest'] = metric['history'][-1]
                metric['series_identity'] = ecos.get('series_identity')
                metric['raw_unit'] = ecos.get('raw_unit')
            else:
                # A current official API series may serve as fallback, but a
                # known newer release failure must remain visible.
                ecos['release_source_error'] = metric.get('error')
                ecos['error'] = metric.get('error')
                ecos['status'] = 'DEGRADED'
                continue
        metrics[key] = metric
    for key, error in release_errors.items():
        (us_errors if key.startswith('US_') else kr_errors)[key] = error
    retain_failed_metrics(metrics, previous)
    vintages = update_vintages(metrics)
    regimes = group_regimes(metrics)

    official_tree = {
        "us": {
            "inflation": {"regime": regimes["us"]["inflation"], "metrics": ["US_CORE_PCE", "US_PCE", "US_CORE_CPI", "US_CPI"]},
            "labor": {"regime": regimes["us"]["labor"], "metrics": ["US_NFP", "US_UNEMPLOYMENT", "US_AHE", "US_JOLTS", "US_ECI"]},
            "growth": {"regime": regimes["us"]["growth"], "metrics": ["US_GDP"]},
            "fed": {"regime": regimes["us"]["fed"], "metrics": ["US_FED_FUNDS", "US_SEP_DOT_PLOT"], "fedwatch_reference": {"meeting_date": fedwatch.get("meeting_date"), "freshness": fedwatch.get("freshness")}},
        },
        "kr": {
            "inflation": {"regime": regimes["kr"]["inflation"], "metrics": ["KR_CPI", "KR_CORE_CPI"]},
            "growth": {"regime": regimes["kr"]["growth"], "metrics": ["KR_GDP", "KR_BOK_OUTLOOK", "KR_INDUSTRIAL_PRODUCTION", "KR_EMPLOYMENT", "KR_BASE_RATE"]},
            "exports": {"regime": regimes["kr"]["exports"], "metrics": ["KR_EXPORT_YOY", "KR_EXPORT_1_20", "KR_CURRENT_ACCOUNT"]},
            "semiconductor": {"regime": regimes["kr"]["semiconductor"], "metrics": ["KR_SEMICON_EXPORT_YOY"]},
        },
    }

    out = {
        "schema": "JJOONI_OFFICIAL_MACRO_V1",
        "generated_kst": now_kst().isoformat(timespec="seconds"),
        "read_only": True,
        "contains_account_data": False,
        "scope": "OFFICIAL_MACRO_ONLY_MARKET_INDICATORS_EXCLUDED",
        "history_target_years": 10,
        "actual_contract": "OFFICIAL_PRIMARY_SOURCE_LOGICAL_SSOT",
        "transport_contract": "FRED_FOR_US_HISTORY_BOK_ECOS_FOR_KR_WHERE_AVAILABLE",
        "consensus_contract": "CONSENSUS_IS_SEPARATE_MARKET_DATA_NOT_OFFICIAL_ACTUAL",
        "revision_contract": "PROSPECTIVE_VINTAGE_LEDGER_NO_OVERWRITE",
        "macro": {"official": official_tree},
        "metrics": metrics,
        "regimes": regimes,
        "portfolio_context": portfolio_context(regimes),
        "historical_markers": [
            {"date": "2020-03-01", "label": "COVID"},
            {"date": "2022-03-01", "label": "Fed tightening"},
            {"date": "2022-06-01", "label": "Inflation peak"},
            {"date": "2024-01-01", "label": "2024~25 disinflation"},
            {"date": "2026-01-01", "label": "2026 reacceleration check"},
        ],
        "quality": {
            "status": "DEGRADED" if any(m.get("status") != "LIVE" for m in metrics.values()) else "LIVE",
            "us_errors": us_errors,
            "kr_errors": kr_errors,
            "live_metrics": sum(1 for x in metrics.values() if x.get("status") == "LIVE"),
            "pending_metrics": [k for k, x in metrics.items() if x.get("status") == "SOURCE_PENDING"],
            "degraded_metrics": [k for k, x in metrics.items() if x.get("status") == "DEGRADED"],
            "vintage_keys": len(vintages.get("vintages", {})),
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OFFICIAL_MACRO_BUILD=PASS")
    print("generated_kst=" + out["generated_kst"])
    print("live_metrics=" + str(out["quality"]["live_metrics"]))
    print("pending=" + ",".join(out["quality"]["pending_metrics"]))


def retain_failed_metrics(metrics, previous):
    for key, metric in list(metrics.items()):
        metric['checked_kst'] = now_kst().isoformat(timespec='seconds')
        if metric.get('status') == 'LIVE':
            metric['last_success_kst'] = metric['checked_kst']
            continue
        old = (previous.get('metrics') or {}).get(key, {})
        if metric.get('latest') and metric.get('history'):
            continue
        if metric.get('series_identity') and old.get('series_identity') != metric['series_identity'] and key not in ('KR_BASE_RATE', 'KR_CPI'):
            continue
        if key == 'KR_CORE_CPI':
            headline = num(((metrics.get('KR_CPI') or {}).get('latest') or {}).get('raw'))
            core = num((old.get('latest') or {}).get('raw'))
            if headline in (None, 0) or core is None or not 0.80 <= core / headline <= 1.20:
                metric['error'] = 'KR_CORE_CPI_RETAINED_SERIES_MISMATCH'
                continue
        if old.get('history') and old.get('latest'):
            saved = copy.deepcopy(old)
            saved.update(status='DEGRADED', checked_kst=metric['checked_kst'],
                         error=metric.get('error') or metric.get('note') or 'SOURCE_UNAVAILABLE',
                         last_success_kst=old.get('last_success_kst') or previous.get('generated_kst'),
                         retained_previous_observation=True)
            metrics[key] = saved


if __name__ == "__main__":
    main()
