#!/usr/bin/env python3
"""Decide whether the Freshness Panel needs its own commit.

The panel runs after every data push AND after nine workflows complete, and
the rebuilt files always differ (generation clock, quote ages), so it
committed 29 times on 2026-11-08 on top of publishers that already embed
fresh health files in their own commits. Commit only when something a reader
acts on changed (overall, per-group state, critical flags, audit counts or
issues, session alignment, as-of dates) or the committed check is older than
MAX_AGE_MIN, so the check clock never goes stale.

Prints publish=true|false and a reason; never fails the job.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRESH = 'market-observatory/data/freshness-status.json'
AUDIT = 'market-observatory/data/data-audit.json'
MAX_AGE_MIN = 30


def committed(path, ref='HEAD'):
    out = subprocess.run(['git', 'show', f'{ref}:{path}'], cwd=ROOT, capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 else None


def fresh_signature(f):
    return {
        'overall': f.get('overall'),
        'critical_bad': f.get('critical_bad'),
        'warnings': f.get('warnings'),
        'session_alignment': f.get('session_alignment'),
        'groups': {k: (g.get('state'), g.get('as_of'), g.get('critical'),
                       {q: v.get('status') for q, v in (g.get('quotes') or {}).items()})
                   for k, g in sorted((f.get('groups') or {}).items())},
    }


def audit_signature(a):
    return {
        'overall': a.get('overall'),
        'critical_count': a.get('critical_count'),
        'warning_count': a.get('warning_count'),
        'issues': a.get('issues'),
        'groups': {k: (g.get('state'), g.get('anchor')) for k, g in sorted((a.get('groups') or {}).items())},
    }


def age_min(doc, now):
    try:
        return (now - datetime.fromisoformat(doc['generated_kst'])).total_seconds() / 60
    except (KeyError, TypeError, ValueError):
        return None


def decide(new_f, new_a, old_f, old_a, now=None):
    now = now or datetime.now(timezone.utc)
    if old_f is None or old_a is None:
        return True, 'no committed health files'
    if fresh_signature(new_f) != fresh_signature(old_f):
        return True, 'freshness state changed'
    if audit_signature(new_a) != audit_signature(old_a):
        return True, 'audit state changed'
    age = age_min(old_f, now)
    if age is None or age >= MAX_AGE_MIN:
        return True, f'committed check is {age if age is None else round(age)} min old'
    return False, f'no state change; committed check {round(age)} min old'


def main():
    try:
        new_f = json.loads((ROOT / FRESH).read_text(encoding='utf-8'))
        new_a = json.loads((ROOT / AUDIT).read_text(encoding='utf-8'))
        publish, reason = decide(new_f, new_a, committed(FRESH, 'origin/main') or committed(FRESH),
                                 committed(AUDIT, 'origin/main') or committed(AUDIT))
    except Exception as exc:  # fail open: publishing is the old, safe behaviour
        publish, reason = True, f'gate error: {exc}'
    print(f'publish={str(publish).lower()}')
    print(f'reason={reason}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
