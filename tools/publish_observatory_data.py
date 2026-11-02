#!/usr/bin/env python3
"""Publish generated files without blindly overwriting concurrent observations.

Calendar conflicts use the same source-ranked merge as collection. Conflicts in
code/UI files stop publication; they are never resolved with `-X theirs`.

A producer can legitimately refresh additional generated JSON files that are
owned by another publishing workflow (for example the 10Y calendar-history
archive while the Market Observatory writer only publishes the live board).
Those *unselected generated JSON* changes are discarded before rebase. Python
cache artifacts created by tests/compilation are also disposable. Code, UI,
workflow, and other non-generated dirty files still fail closed.
"""
import argparse
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from observatory_history_views import materialize
from calendar_history_integrity import merge_history_documents
from calendar_actual_contract import KST, build_freshness, merge_observation, retain_calendar

ROOT = Path(__file__).resolve().parents[1]
DATA = 'market-observatory/data/'
MARKET_BUNDLE = (DATA + 'observatory.json', DATA + 'daily-market-pulse.json', 'public-market-daily.json')


def publication_paths(paths):
    """Declare the market dependency group once for every publisher.

    Independent crypto/rate collectors can publish observatory.json alone.
    Publishing either daily consumer always includes its canonical source and
    sibling consumer. Thus a source merge cannot leave a stale TRI-POD/pulse.
    """
    paths = list(dict.fromkeys(paths))
    for path in paths:
        generated_view=path in (DATA+'fedwatch-history/brief.md',DATA+'fedwatch-history/probabilities.csv')
        if (not str(path).endswith('.json') and not generated_view) or '..' in Path(path).parts or not (str(path).startswith(DATA) or path=='public-market-daily.json'):
            raise ValueError('DATA_PUBLISHER_REJECTED_NON_DATA_PATH: '+str(path))
    if set(paths).intersection(MARKET_BUNDLE[1:]):
        paths = list(dict.fromkeys([*paths, *MARKET_BUNDLE]))
    # GitHub Actions bot commits do not reliably trigger downstream push workflows.
    # Publish the audit and freshness verdict in the SAME commit as any canonical
    # market-source update, including independent 24/7 BTC/ETH quote refreshes.
    # materialize_health() recomputes both after every concurrent-source rebase.
    if DATA + 'observatory.json' in paths:
        paths = list(dict.fromkeys([*paths, DATA + 'data-audit.json', DATA + 'freshness-status.json']))
    return paths


def git(*args, check=True):
    return subprocess.run(['git', *args], cwd=ROOT, text=True, capture_output=True, check=check)


def merge_generated(path, local, remote):
    if path.endswith('/observatory.json'):
        result = deepcopy(max((remote, local), key=lambda doc: (str(doc.get('us_completed_session_date') or ''), str(doc.get('generated_kst') or ''))))
        for key in ('BTCUSD', 'ETHUSD'):
            candidates = [doc for doc in (remote, local) if (doc.get('crypto_market') or {}).get(key) and (doc.get('series') or {}).get(key)]
            if not candidates:
                continue
            def quote_key(doc):
                q = doc['crypto_market'][key]
                return str(q.get('quote_as_of_kst') or ''), str(q.get('last_attempt_kst') or q.get('captured_kst') or '')
            winner = max(candidates, key=quote_key)
            result.setdefault('crypto_market', {})[key] = deepcopy(winner['crypto_market'][key])
            result.setdefault('series', {})[key] = deepcopy(winner['series'][key])
            result.setdefault('latest', {})[key] = result['series'][key][-1]['value']
            if (winner.get('sources') or {}).get('CRYPTO_SPOT'):
                result.setdefault('sources', {})['CRYPTO_SPOT'] = winner['sources']['CRYPTO_SPOT']
            if winner.get('crypto_contract'):
                result['crypto_contract'] = winner['crypto_contract']
        # Supplemental collectors own a separate attempt clock. Preserve their
        # observations only for the same US session; never mix session anchors.
        supplemental=max((remote,local),key=lambda doc:str(doc.get('supplemental_refreshed_kst') or ''))
        if supplemental.get('supplemental_refreshed_kst') and supplemental.get('us_completed_session_date') == result.get('us_completed_session_date'):
            result['supplemental_refreshed_kst']=supplemental['supplemental_refreshed_kst']
            result['supplemental_refresh_contract']=supplemental.get('supplemental_refresh_contract')
            owned=('NASDAQ100','SP500','VIX','RUSSELL2000','DOW','NASDAQCOMPOSITE','DXY','USDKRW','USDJPY','JPYKRW','WTI','BRENT','NATGAS','GOLD','SILVER','COPPER','KOSPI','KOSDAQ','FEAR_GREED','JP2Y','JP5Y','JP10Y','JP30Y','JP_2S10S')
            jp_owned={'JP2Y','JP5Y','JP10Y','JP30Y','JP_2S10S'}
            for key in owned:
                if key in jp_owned:
                    # An older supplemental attempt must not erase a newly
                    # published official MOF date. Existing main observations
                    # take precedence on overlap; append only missing dates.
                    merged={}
                    for doc in (local,remote):
                        for row in (doc.get('series') or {}).get(key,[]):
                            if row.get('date') and row.get('value') is not None:
                                merged[str(row['date'])]=deepcopy(row)
                    if merged:
                        rows=[merged[d] for d in sorted(merged)]
                        result.setdefault('series',{})[key]=rows
                        result.setdefault('latest',{})[key]=rows[-1]['value']
                else:
                    rows=(supplemental.get('series') or {}).get(key)
                    if rows:
                        result.setdefault('series',{})[key]=deepcopy(rows)
                        result.setdefault('latest',{})[key]=rows[-1]['value']
                for section in ('cross_market_freshness_quality','market_supplement_quality'):
                    quality=(supplemental.get(section) or {}).get(key)
                    if quality is not None:result.setdefault(section,{})[key]=deepcopy(quality)
            jp_quality=(supplemental.get('cross_market_freshness_quality') or {}).get('JP_RATES')
            if jp_quality is not None:
                quality=deepcopy(jp_quality)
                dates=[str((result.get('series') or {}).get(k, [{}])[-1].get('date') or '') for k in ('JP2Y','JP5Y','JP10Y','JP30Y')]
                latest_jp=min(dates) if all(dates) else ''
                if latest_jp and latest_jp>str(quality.get('last_date') or ''):
                    quality['last_date']=latest_jp
                    expected=str(quality.get('expected_latest_weekday') or '')
                    quality['status']='LIVE' if expected and latest_jp>=expected else 'LAGGING'
                    # The merged observation may originate from either official
                    # mirror; do not retain a stale mirror-specific source URL.
                    quality.pop('source_url',None)
                    quality['source']='Japan MOF official JGB CSV (merged)'
                result.setdefault('cross_market_freshness_quality',{})['JP_RATES']=quality
            jp_source=(supplemental.get('sources') or {}).get('JP_JGB_CURRENT')
            if jp_source:result.setdefault('sources',{})['JP_JGB_CURRENT']=jp_source
        # A daily producer may advance generated_kst while the independent KR
        # collector is running. Preserve its newer attempt and verified curve.
        kr_winner=max((remote,local),key=lambda doc:str(doc.get('kr_rates_refreshed_kst') or ''))
        if kr_winner.get('kr_rates_refreshed_kst'):
            result['kr_rates_refreshed_kst']=kr_winner['kr_rates_refreshed_kst']
            for key in ('KR3Y','KR5Y','KR10Y','KR20Y','KR30Y','KR_3S10S'):
                rows={str(r['date']):deepcopy(r) for doc in (remote,local) for r in (doc.get('series') or {}).get(key,[]) if r.get('date') and r.get('value') is not None}
                # Newer KR attempt wins any same-date official correction.
                rows.update({str(r['date']):deepcopy(r) for r in (kr_winner.get('series') or {}).get(key,[]) if r.get('date') and r.get('value') is not None})
                if rows:
                    result.setdefault('series',{})[key]=[rows[d] for d in sorted(rows)]
                    result.setdefault('latest',{})[key]=result['series'][key][-1]['value']
            for key in ('KR3Y','KR5Y','KR10Y','KR20Y','KR30Y','KR_RATES'):
                q=(kr_winner.get('cross_market_freshness_quality') or {}).get(key)
                if q is not None:result.setdefault('cross_market_freshness_quality',{})[key]=deepcopy(q)
            source=(kr_winner.get('sources') or {}).get('KR_RATES_CURRENT')
            if source:result.setdefault('sources',{})['KR_RATES_CURRENT']=source
        # US card yields have their own attempt clock, independent of equities
        # and the heavy daily producer. Preserve rows across concurrent writers.
        us_winner=max((remote,local),key=lambda doc:str(doc.get('us_rates_refreshed_kst') or ''))
        if us_winner.get('us_rates_refreshed_kst'):
            result['us_rates_refreshed_kst']=us_winner['us_rates_refreshed_kst']
            for key in ('US2Y','US3M','US5Y_OFFICIAL','US10Y_OFFICIAL','US30Y_OFFICIAL','US5Y','US10Y','US30Y','US_2S10S'):
                rows={str(r['date']):deepcopy(r) for doc in (remote,local,us_winner) for r in (doc.get('series') or {}).get(key,[]) if r.get('date') and r.get('value') is not None}
                if rows:
                    result.setdefault('series',{})[key]=[rows[d] for d in sorted(rows)]
                    result.setdefault('latest',{})[key]=result['series'][key][-1]['value']
                q=(us_winner.get('cross_market_freshness_quality') or {}).get(key)
                if q is not None:result.setdefault('cross_market_freshness_quality',{})[key]=deepcopy(q)
        if local.get('crypto_enriched_kst') or remote.get('crypto_enriched_kst'):
            result['crypto_enriched_kst'] = max(str(local.get('crypto_enriched_kst') or ''), str(remote.get('crypto_enriched_kst') or ''))
        return result
    if path.endswith('/fed-watch.json') or path.endswith('/fedwatch-official.json'):
        # An older fallback cannot replace a newer official observation.
        return deepcopy(max((remote, local), key=lambda doc: (str(doc.get('market_data_as_of') or ''), doc.get('source_kind') == 'CME_OFFICIAL_PUBLIC_TABLE', str(doc.get('source_as_of_ct') or ''), str(doc.get('generated_kst') or ''))))
    if path.endswith('/fedwatch-history/index.json'):
        entries={}
        for doc in (remote,local):
            for row in doc.get('entries') or []:
                day=row['market_data_as_of']
                revisions={r['sha256']:r for r in (entries.get(day,{}).get('revisions') or [])}
                revisions.update({r['sha256']:deepcopy(r) for r in row.get('revisions') or []})
                if not revisions:continue
                ordered=sorted(revisions.values(),key=lambda r:(r.get('source_kind')=='CME_OFFICIAL_PUBLIC_TABLE',r['generated_kst'],r['sha256']))
                selected=ordered[-1]
                entries[day]={'market_data_as_of':day,'path':selected['path'],'generated_kst':selected['generated_kst'],'revisions':ordered}
        return {**deepcopy(remote),**deepcopy(local),'entries':[entries[d] for d in sorted(entries,reverse=True)]}
    if path.endswith('/economic-calendar-history.json'):
        return merge_history_documents(local, remote)
    if path.endswith('/economic-calendar.json'):
        result = retain_calendar(deepcopy(local), remote)
        checks = result.get('actual_freshness', {}).get('official_checks', [])
        result['actual_freshness'] = build_freshness(result, datetime.now(KST), checks)
        return result
    if path.endswith('/calendar-manual-overrides.json'):
        result = deepcopy(local)
        def key(row):
            match = row.get('match', {})
            return match.get('date'), match.get('country'), match.get('title_contains')
        rows = {key(row): row for row in remote.get('overrides', [])}
        for row in local.get('overrides', []):
            old = rows.get(key(row), {})
            merged = merge_observation(old, row)
            if old.get('event') or row.get('event'):
                merged['event'] = merge_observation(old.get('event', {}), row.get('event', {}))
            rows[key(row)] = merged
        result['overrides'] = list(rows.values())
        return result
    if path.endswith('/calendar-official-release-cache.json'):
        return {**local, 'documents': {**remote.get('documents', {}), **local.get('documents', {})}}
    if path.endswith('/pulse-history/index.json'):
        result = deepcopy(local)
        rows = {r['snapshot_id']: r for r in remote.get('observations', [])}
        rows.update({r['snapshot_id']: r for r in local.get('observations', [])})
        result['observations'] = sorted(rows.values(), key=lambda r: (str(r.get('market_date_us')), str(r.get('generated_kst')), r['snapshot_id']))
        return result
    if str(remote.get('generated_kst', '')) > str(local.get('generated_kst', '')):
        return remote
    return local


def parse_porcelain(output):
    """Return (status, path) pairs from `git status --porcelain=v1`."""
    out = []
    for raw in str(output or '').splitlines():
        if len(raw) < 4:
            continue
        status = raw[:2]
        path = raw[3:]
        if ' -> ' in path:
            path = path.split(' -> ', 1)[1]
        out.append((status, path))
    return out


def is_ephemeral_build_artifact(path):
    """Artifacts created by Python test/compile steps that are safe to drop."""
    p = str(path or '').replace('\\', '/')
    return (
        '/__pycache__/' in '/' + p
        or p.endswith(('.pyc', '.pyo', '.pyd'))
        or '/.pytest_cache/' in '/' + p
        or p.startswith('.pytest_cache/')
    )


def clean_unselected_generated(selected_paths):
    """Make the worktree rebase-safe without hiding source/UI changes."""
    selected = set(selected_paths)
    entries = parse_porcelain(git('status', '--porcelain=v1', '--untracked-files=all').stdout)
    discard = []
    ephemeral = []
    unsafe = []
    for status, path in entries:
        if path in selected:
            unsafe.append((status, path))
        elif path.startswith(DATA) and path.endswith('.json'):
            discard.append((status, path))
        elif status == '??' and is_ephemeral_build_artifact(path):
            ephemeral.append((status, path))
        else:
            unsafe.append((status, path))
    if unsafe:
        details = ', '.join(f'{status}:{path}' for status, path in unsafe)
        raise RuntimeError('Uncommitted non-selected/non-generated change requires review: ' + details)
    tracked = [path for status, path in discard if status != '??']
    untracked = [path for status, path in discard + ephemeral if status == '??']
    if tracked:
        git('restore', '--worktree', '--', *tracked)
    for path in untracked:
        p = ROOT / path
        if p.is_file():
            p.unlink()
    if discard:
        print('OBSERVATORY_PUBLISH_DISCARD_UNSELECTED_GENERATED=' + ','.join(path for _, path in discard))
    if ephemeral:
        print('OBSERVATORY_PUBLISH_DISCARD_EPHEMERAL=' + str(len(ephemeral)))
    return [path for _, path in discard + ephemeral]


def materialize_market_dependents(paths):
    """Build consumers from the exact source snapshot before audit and after rebase."""
    required = {DATA + 'observatory.json', DATA + 'daily-market-pulse.json', 'public-market-daily.json'}
    if not required.issubset(set(paths)):
        return
    import build_daily_market_pulse as pulse
    import build_public_market_daily as public
    obs = json.loads((ROOT / (DATA + 'observatory.json')).read_text(encoding='utf-8'))
    # Explicit paths prevent one publication/worktree from mutating another
    # builder's module globals in a long-lived process.
    public_out = ROOT / 'public-market-daily.json'
    pulse_out = ROOT / DATA / 'daily-market-pulse.json'
    public.main(observatory=obs, out=public_out)
    pulse.main(offline=True, data_dir=ROOT / DATA, out=pulse_out)
    from build_market_observatory import tripod_history
    from postprocess_market_observatory import build_today_strategy
    sidecar = json.loads(public_out.read_text(encoding='utf-8'))
    report = json.loads(pulse_out.read_text(encoding='utf-8'))
    obs['tripod_latest'] = sidecar['tripod_signal']
    history, signals = tripod_history(obs['series'])
    obs['tripod_history'] = history[-800:]
    obs['signal_log'] = signals[-100:]
    obs['today_strategy'] = build_today_strategy(obs, report)
    obs['today_strategy_contract'] = 'TRIPOD_CANONICAL_DECISION_SUPPORT_V1'
    (ROOT / (DATA + 'observatory.json')).write_text(json.dumps(obs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def materialize_health(paths):
    """Derive health from the exact merged sources, never carry an old audit."""
    health = {DATA + 'data-audit.json', DATA + 'freshness-status.json'}
    if health.issubset(set(paths)):
        for script in ('audit_observatory_data.py', 'build_observatory_freshness.py'):
            subprocess.run([sys.executable, str(ROOT / 'tools' / script)], cwd=ROOT,
                           check=True, capture_output=True, text=True)


def materialize_publication(paths):
    """One order before commit AND after every rebase: derive, archive, audit."""
    materialize_market_dependents(paths)
    paths = list(dict.fromkeys([*paths, *materialize(ROOT, paths)]))
    if DATA+'fed-watch.json' in paths and DATA+'fedwatch-history/index.json' in paths:
        from archive_fedwatch import archive_snapshot
        archive_snapshot(json.loads((ROOT/(DATA+'fed-watch.json')).read_text()), ROOT/DATA)
        paths = list(dict.fromkeys([*paths, *(str(p.relative_to(ROOT)) for p in
                     (ROOT/(DATA+'fedwatch-history')).rglob('*') if p.is_file())]))
    materialize_health(paths)
    return paths


def publish(paths, message):
    paths = materialize_publication(publication_paths(paths))
    for path in paths:
        if not (ROOT / path).is_file():
            raise ValueError(f'Publish path missing: {path}')
    git('add', '--', *paths)
    if git('diff', '--cached', '--quiet', check=False).returncode == 0:
        print('OBSERVATORY_PUBLISH=NO_CHANGE')
        return
    git('commit', '-m', message)
    clean_unselected_generated(paths)

    for attempt in range(3):
        git('fetch', 'origin', 'main')
        payloads = {}
        for path in paths:
            if path in {DATA+'fedwatch-history/brief.md',DATA+'fedwatch-history/probabilities.csv',DATA+'observatory-recent.json'}:
                # These are deterministic views, regenerated from the merged
                # archive after rebase. Only these exact generated paths qualify.
                remote_view=git('show','origin/main:'+path,check=False)
                payloads[path]=remote_view.stdout if remote_view.returncode==0 else (ROOT/path).read_text(encoding='utf-8')
                continue
            if (not path.startswith(DATA) and path != 'public-market-daily.json') or not path.endswith('.json'):
                continue
            remote = git('show', 'origin/main:' + path, check=False)
            local = json.loads((ROOT / path).read_text(encoding='utf-8'))
            merged = merge_generated(path, local, json.loads(remote.stdout)) if remote.returncode == 0 else local
            payloads[path] = json.dumps(merged, ensure_ascii=False, indent=2) + '\n'
        result = git('rebase', 'origin/main', check=False)
        while result.returncode:
            conflicts = git('diff', '--name-only', '--diff-filter=U').stdout.splitlines()
            if not conflicts:
                error = (result.stderr or result.stdout or 'unknown rebase error').strip().replace('\n', ' | ')
                git('rebase', '--abort', check=False)
                raise RuntimeError('Rebase failed without merge conflicts: ' + error)
            if any(path not in payloads for path in conflicts):
                git('rebase', '--abort', check=False)
                raise RuntimeError('Concurrent non-data change requires review: ' + ', '.join(conflicts))
            for path in conflicts:
                (ROOT / path).write_text(payloads[path], encoding='utf-8')
            git('add', '--', *conflicts)
            result = git('-c', 'core.editor=true', 'rebase', '--continue', check=False)
        for path, payload in payloads.items():
            (ROOT / path).write_text(payload, encoding='utf-8')
        paths = materialize_publication(paths)
        git('add', '--', *paths)
        if git('diff', '--cached', '--quiet', check=False).returncode:
            git('commit', '-m', 'data(observatory): preserve concurrent official observations')
        if git('push', 'origin', 'HEAD:main', check=False).returncode == 0:
            print('OBSERVATORY_PUBLISH=PASS commit=' + git('rev-parse', 'HEAD').stdout.strip())
            return
        print(f'OBSERVATORY_PUBLISH_RETRY={attempt+1}')
    raise RuntimeError('Publication failed after three concurrent-update retries')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--message', required=True)
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    publish(args.paths, args.message)


