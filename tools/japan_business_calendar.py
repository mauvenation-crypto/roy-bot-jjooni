#!/usr/bin/env python3
"""Dependency-free Tokyo JGB market calendar (2022-2099).

Japan MOF publishes no JGB yield for national holidays or the year-end/new
year market closure (Dec 31, Jan 1-3). Treating those days as business days
made the JP rates freshness grade LAGGING on every Japanese holiday even
though the official source was complete.

Rules follow the National Holidays Act as amended for 2020+:
fixed-date holidays, Happy Monday holidays, astronomical equinox
approximation, substitute holidays (振替休日) and citizens' holidays
(国民の休日). Ad-hoc one-off holidays (e.g. imperial events) must be added to
EXTRA_HOLIDAYS when the government announces them.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

# One-off holidays announced by law. Extend when announced.
EXTRA_HOLIDAYS: frozenset[date] = frozenset()


def _nth_monday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (7 - first.weekday()) % 7  # Monday == 0
    return first + timedelta(days=offset + 7 * (n - 1))


def _vernal_equinox(year: int) -> date:
    return date(year, 3, int(20.8431 + 0.242194 * (year - 1980) - (year - 1980) // 4))


def _autumnal_equinox(year: int) -> date:
    return date(year, 9, int(23.2488 + 0.242194 * (year - 1980) - (year - 1980) // 4))


@lru_cache(maxsize=None)
def national_holidays(year: int) -> frozenset[date]:
    if not 2022 <= year <= 2099:
        raise ValueError('JP_HOLIDAY_RULES_COVER_2022_2099')
    base = {
        date(year, 1, 1),                 # 元日
        _nth_monday(year, 1, 2),          # 成人の日
        date(year, 2, 11),                # 建国記念の日
        date(year, 2, 23),                # 天皇誕生日
        _vernal_equinox(year),            # 春分の日
        date(year, 4, 29),                # 昭和の日
        date(year, 5, 3), date(year, 5, 4), date(year, 5, 5),
        _nth_monday(year, 7, 3),          # 海の日
        date(year, 8, 11),                # 山の日
        _nth_monday(year, 9, 3),          # 敬老の日
        _autumnal_equinox(year),          # 秋分の日
        _nth_monday(year, 10, 2),         # スポーツの日
        date(year, 11, 3),                # 文化の日
        date(year, 11, 23),               # 勤労感謝の日
    }
    base |= {d for d in EXTRA_HOLIDAYS if d.year == year}
    holidays = set(base)
    # 国民の休日: a weekday sandwiched between two holidays.
    for d in sorted(base):
        mid = d + timedelta(days=1)
        if mid not in holidays and (d + timedelta(days=2)) in base and mid.weekday() != 6:
            holidays.add(mid)
    # 振替休日: a Sunday holiday moves to the next non-holiday day.
    for d in sorted(base):
        if d.weekday() == 6:
            sub = d + timedelta(days=1)
            while sub in holidays:
                sub += timedelta(days=1)
            holidays.add(sub)
    return frozenset(holidays)


def is_jgb_market_holiday(day: date) -> bool:
    if (day.month, day.day) in {(12, 31), (1, 1), (1, 2), (1, 3)}:
        return True
    return day in national_holidays(day.year)


def is_jgb_business_day(day: date) -> bool:
    return day.weekday() < 5 and not is_jgb_market_holiday(day)


def previous_jgb_business_day(day: date) -> date:
    day -= timedelta(days=1)
    while not is_jgb_business_day(day):
        day -= timedelta(days=1)
    return day
