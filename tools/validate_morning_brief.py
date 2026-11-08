#!/usr/bin/env python3
"""Validate the published morning brief and its dated archive without market estimation."""
from __future__ import annotations
import argparse
import json
import re
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlparse
from observatory_session import expected_completed_session

EDITORIAL_SECTIONS = [
    '① 오늘의 시장 이야기', '② 시장 한눈에', '③ 핵심 이슈 깊이 읽기',
    '④ 글로벌·한국 시장', '⑤ AI 산업·기업실적', '⑥ 주요 일정',
    '⑦ 투자전략·위험점검·복기', '⑧ 원천·데이터 감사',
]

def validate_editorial(d, created):
    """Keep the new daily format and close proof from silently reverting."""
    if d['report_date_kst'] < '2026-11-03':
        return  # Dated historical reports retain their original presentation.
    contract = d.get('editorial_contract') or {}
    assert contract.get('version') == 'SONG_INSPIRED_DAILY_V1', 'EDITORIAL_VERSION'
    body = d['body_markdown']
    assert re.findall(r'^##\s+(.+)$', body, re.M) == EDITORIAL_SECTIONS, 'EDITORIAL_SECTIONS'
    for label in ('핵심 숫자', '무슨 일이 있었나', '왜 중요한가', '반대 해석', '다음 확인'):
        assert body.count('**' + label + ':**') >= 3, ('ISSUE_EXPLANATION_MISSING', label)
    checked = datetime.fromisoformat(contract['verified_at_kst'])
    assert checked.utcoffset() == timedelta(hours=9) and checked <= created, 'VERIFICATION_CLOCK'
    assert d['market_date_us'] <= expected_completed_session(checked), 'UNFINISHED_US_SESSION'
    checks = contract.get('close_checks') or []
    assert {x.get('symbol') for x in checks} == {'NDX', 'SOX'}, 'CORE_CLOSE_COVERAGE'
    for check in checks:
        assert check.get('session_date') == d['market_date_us'], 'CLOSE_SESSION_MISMATCH'
        post_audit=check.get('post_publication_verified_at_kst')
        if post_audit:
            revised=datetime.fromisoformat(post_audit)
            assert revised.utcoffset() == timedelta(hours=9) and revised > created, 'POST_PUBLICATION_CLOCK'
            assert contract.get('verification_updated_kst') == post_audit, 'POST_PUBLICATION_VERSION'
            matching=[r for r in d.get('revisions', []) if
                      r.get('field') == 'editorial_contract.close_checks['+check['symbol']+']' and
                      r.get('revised_at_kst') == post_audit and
                      len(set(r.get('source_urls') or [])) >= 2]
            assert matching, 'POST_PUBLICATION_PROOF_TRAIL'
        assert check.get('status') in {'VERIFIED', 'MISSING', 'CONFLICT', 'CROSS_CHECKED'}, 'CLOSE_STATUS'
        if check['status'] == 'CROSS_CHECKED':
            assert check.get('reason') and check.get('official_status') == 'NOT_CHECKED', 'CROSS_CHECK_DISCLOSURE'
            close, previous = check.get('close'), check.get('previous_close')
            assert all(isinstance(v, (int, float)) and 0 < v < float('inf') for v in (close, previous)), 'CLOSE_VALUE'
            assert abs((close / previous - 1) * 100 - check['change_pct']) < .01, 'CLOSE_RETURN_ARITHMETIC'
            observations = check.get('source_observations') or []
            valid = []
            postclose = False
            for obs in observations:
                url = obs.get('url') or ''
                host = urlparse(url).hostname if urlparse(url).scheme == 'https' else None
                if not host or url not in (check.get('source_urls') or []): continue
                if obs.get('session_date') != check['session_date'] or obs.get('close') != close: continue
                if obs.get('observation_type') not in ('COMPLETED_DAILY_BAR','POST_CLOSE_QUOTE'): continue
                observed = obs.get('observed_at')
                if observed:
                    stamp = datetime.fromisoformat(observed)
                    assert stamp.tzinfo and stamp <= checked, 'CROSS_CHECK_CLOCK'
                    ny = stamp.astimezone(ZoneInfo('America/New_York'))
                    if ny.date().isoformat() != check['session_date'] or ny.time() < time(16,0):
                        continue
                    postclose = True
                elif obs.get('observation_type') != 'COMPLETED_DAILY_BAR':
                    continue
                valid.append(host)
            assert len(set(valid)) >= 2 and postclose, 'CROSS_CHECK_SOURCES_OR_SESSION'
            continue
        if check['status'] != 'VERIFIED':
            assert check.get('reason'), 'UNVERIFIED_CLOSE_REASON'
            continue
        close, previous = check['close'], check['previous_close']
        assert all(isinstance(v, (int, float)) and 0 < v < float('inf') for v in (close, previous)), 'CLOSE_VALUE'
        assert abs((close / previous - 1) * 100 - check['change_pct']) < .01, 'CLOSE_RETURN_ARITHMETIC'
        urls = check.get('source_urls') or []
        hosts = {urlparse(u).hostname for u in urls if urlparse(u).scheme == 'https'}
        assert len(hosts) >= 2 and any(h and (h == 'nasdaq.com' or h.endswith('.nasdaq.com')) for h in hosts), 'INDEPENDENT_CLOSE_SOURCES'
        assert check.get('observation_type') == 'REGULAR_SESSION_CLOSE', 'CLOSE_OBSERVATION_TYPE'
    return d

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def validate_report(d):
    assert d.get('schema') == 'JJOONI_MORNING_BRIEF_V1', 'BRIEF_SCHEMA'
    assert d.get('read_only') is True and d.get('contains_account_data') is False, 'BRIEF_PUBLIC_BOUNDARY'
    report_day = date.fromisoformat(d['report_date_kst'])
    assert date.fromisoformat(d['market_date_us']) <= report_day, 'MARKET_DATE_AFTER_REPORT'
    created = datetime.fromisoformat(d['generated_kst'])
    published = datetime.fromisoformat(d['published_kst'])
    assert created.utcoffset() == published.utcoffset() == timedelta(hours=9), 'KST_OFFSET'
    assert created.date() == report_day and published >= created, 'REPORT_TIMESTAMPS'
    assert d.get('content_status') in {'USER_PROVIDED_NOT_REVERIFIED', 'WEB_VERIFIED_WITH_DISCLOSED_GAPS'}, 'CONTENT_STATUS'
    assert isinstance(d.get('verification_note'), str) and d['verification_note'].strip(), 'VERIFICATION_NOTE'
    body = d.get('body_markdown')
    assert isinstance(body, str) and 500 <= len(body) <= 200_000, 'BODY_LENGTH'
    sections = re.findall(r'^##\s+([①②③④⑤⑥⑦⑧])', body, re.M)
    assert sections == list('①②③④⑤⑥⑦⑧'), ('EIGHT_SECTIONS', sections)
    assert re.search(r'\[[^\]\n]+\]\(https?://[^\s)]+\)', body), 'SOURCE_LINKS'
    assert '' not in body, 'CHAT_ONLY_CITATION_TOKEN'
    validate_editorial(d, created)
    return d

def validate_directory(directory):
    latest = validate_report(read(directory / 'latest.json'))
    index = read(directory / 'index.json')
    assert index.get('schema') == 'JJOONI_MORNING_BRIEF_INDEX_V1', 'INDEX_SCHEMA'
    entries = index.get('entries')
    assert isinstance(entries, list) and entries, 'EMPTY_INDEX'
    days = [e['report_date_kst'] for e in entries]
    assert days == sorted(set(days), reverse=True), 'INDEX_ORDER_OR_DUPLICATE'
    assert latest['report_date_kst'] == days[0], 'LATEST_NOT_MOST_RECENT'
    for entry in entries:
        day = date.fromisoformat(entry['report_date_kst'])
        path = day.strftime('%Y%m%d') + '.json'
        assert entry.get('path') == path, 'ARCHIVE_PATH'
        archived = validate_report(read(directory / path))
        for key in ('report_date_kst', 'market_date_us', 'title', 'generated_kst', 'published_kst'):
            assert archived.get(key) == entry.get(key), ('INDEX_ARCHIVE_MISMATCH', key)
        if entry['report_date_kst'] == latest['report_date_kst']:
            assert archived == latest, 'LATEST_ARCHIVE_MISMATCH'
    print('MORNING_BRIEF_ACCEPTANCE=PASS', 'latest='+latest['report_date_kst'], 'archives='+str(len(entries)))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1] / 'market-observatory' / 'data' / 'morning-brief')
    validate_directory(parser.parse_args().directory)
