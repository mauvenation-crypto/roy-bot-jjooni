"""Date label for a Yahoo chart daily bar.

Yahoo stamps each daily bar at the session open in the instrument's own
exchange time zone (``meta.exchangeTimezoneName``). For FX (``KRW=X``,
``JPY=X``, ...) that is 00:00 Europe/London, which is 19:00/20:00 of the
PREVIOUS day in New York. Labelling every bar in America/New_York therefore
shifted all FX rows one day back (Sun-Thu labels, never Friday). US indices
and futures already live in America/New_York, so their dates are unchanged.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')


def exchange_tz(result, default=ET):
    name = ((result or {}).get('meta') or {}).get('exchangeTimezoneName')
    if name:
        try:
            return ZoneInfo(str(name))
        except Exception:
            pass
    return default


def bar_date(stamp, result, default=ET):
    return datetime.fromtimestamp(int(stamp), exchange_tz(result, default)).date().isoformat()
