"""Date-locked ECI headline fallback: BLS release identity, FRED transport.

Only the 2026-10-30 release is approved by this registry. FRED is a
transport for the BLS ECIALLCIV series, not a substitute for an
unverified release or an excuse to rewrite historical wage-only vintages.
Both as-released index levels must match BLS Table 1 exactly.
"""
import csv
import io
import re
import urllib.request
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
SERIES = "ECIALLCIV"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=ECIALLCIV&cosd=2026-04-01"
RELEASES = {
    "2026-10-30": {
        "period": "2026-09",
        "label": "September 2026 Employment Cost Index",
        "bls_url": "https://www.bls.gov/news.release/archives/eci_10302026.htm",
        # Exact seasonally adjusted civilian total compensation levels
        # from BLS's 2026-10-30 Table 1, not the wage-only series.
        "index": {"2026-04-01": Decimal("177.178"),
                  "2026-07-01": Decimal("178.574")},
        "qoq": Decimal("0.8"),
    }
}


def parse_verified_csv(raw, release):
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or SERIES not in reader.fieldnames:
        raise ValueError("ECI_SERIES_IDENTITY_MISSING")
    date_field = next((x for x in ("DATE", "observation_date", "date")
                       if x in reader.fieldnames), None)
    if date_field is None:
        raise ValueError("ECI_DATE_COLUMN_MISSING")
    values = {}
    expected = release["index"]
    for row in reader:
        date = row.get(date_field)
        if date not in expected:
            continue
        value = str(row.get(SERIES) or "").strip()
        if not re.fullmatch(r"\d+(?:\.\d+)?", value):
            raise ValueError("ECI_INDEX_INVALID")
        if date in values:
            raise ValueError("ECI_DUPLICATE_QUARTER")
        values[date] = Decimal(value)
    if set(values) != set(expected):
        raise ValueError("ECI_REFERENCE_QUARTER_MISSING")
    if any(values[k] != v for k, v in expected.items()):
        raise ValueError("ECI_BLS_TABLE1_FRED_VINTAGE_MISMATCH")
    qoq = ((values["2026-07-01"] / values["2026-04-01"] - 1)
           * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if qoq != release["qoq"]:
        raise ValueError("ECI_HEADLINE_QOQ_MISMATCH")
    return f"{qoq:.1f}%"


def fetch_csv():
    request = urllib.request.Request(
        FRED_URL, headers={"User-Agent": "Mozilla/5.0 JJOONI-ECI/1.0",
                           "Accept": "text/csv"})
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.read().decode("utf-8-sig")


def collect_eci_fred(event, checks):
    from calendar_actual_contract import release_time
    if event.get("country") != "US" or event.get("title") != "Employment Cost Index":
        checks.append({"adapter": "ECI_FRED", "result": "EVENT_IDENTITY_MISMATCH"})
        return None
    released = release_time(event).astimezone(NY).date().isoformat()
    entry = RELEASES.get(released)
    if not entry:
        checks.append({"adapter": "ECI_FRED", "result": "RELEASE_NOT_VERIFIED",
                       "release_date": released})
        return None
    old_period = str(event.get("reference_period") or "").strip()
    if old_period not in ("", entry["period"], entry["label"]):
        checks.append({"adapter": "ECI_FRED", "result": "REFERENCE_PERIOD_MISMATCH",
                       "reference_period": old_period})
        return None
    try:
        actual = parse_verified_csv(fetch_csv(), entry)
    except Exception as exc:
        checks.append({"adapter": "ECI_FRED", "result": type(exc).__name__,
                       "error": str(exc)[:200], "url": FRED_URL})
        return None
    event["reference_period"] = entry["label"]
    row = {"key": "eci", "label": "Employment Cost Index (civilian total compensation, SA QoQ)",
           "actual": actual, "source": "BLS ECI Table 1 cross-checked via FRED ECIALLCIV",
           "source_url": FRED_URL, "official_url": entry["bls_url"],
           "source_tier": "OFFICIAL", "verification_status": "VERIFIED_OFFICIAL",
           "value_vintage": "AS_RELEASED", "reference_period": entry["period"],
           "series_id": SERIES}
    checks.append({"adapter": "ECI_FRED", "result": "VERIFIED_BLS_TABLE1_FRED_MATCH",
                   "url": FRED_URL, "bls_url": entry["bls_url"],
                   "reference_period": entry["period"], "actual": actual})
    return [row], FRED_URL
