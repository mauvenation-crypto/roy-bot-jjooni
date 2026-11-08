"""Quarantine market values copied across metrics before the #236 identity guard.

Until 2026-10-29 the generic all-event matcher could accept a market-feed row
whose direction differed from the metric (``Average Hourly Earnings m/m`` was
written into ``avg_hourly_yoy``, ``Import Prices m/m`` into the export metric).
#236 stopped new cross-matches, but ``merge_observation`` never erases stored
facts, so the copied values survived. Worse, a contaminated metric looks
complete, so the official collector never revisits the release.

Signature of a copied value: the metric's market fields came through the
generic path (``generic_match_score`` without a recorded ``event_title``), and
the field equals the same field of a sibling metric whose identity is
incompatible with this metric (MoM vs YoY, import vs export). Such fields are
cleared and kept under ``quarantined_values`` for audit; official values are
never touched.
"""
from calendar_actual_contract import PROVENANCE, clean
from enrich_calendar_all_events import metric_identity_compatible

REASON = 'CROSS_METRIC_COPY_BEFORE_IDENTITY_GUARD'
FIELDS = ('actual', 'consensus', 'previous')
MARKET_TIERS = {'MARKET_FEED', 'SECONDARY'}


def _legacy_generic(metric):
    return metric.get('generic_match_score') is not None and not clean(metric.get('event_title'))


def _sibling_title(metric):
    return clean(metric.get('event_title')) or clean(metric.get('label')) or clean(metric.get('key')) or ''


def _owns_value_over(sibling, metric):
    """Whether ``sibling`` is the credible origin of a value both metrics share."""
    if clean(sibling.get('event_title')) or not _legacy_generic(sibling):
        return True
    # Both legacy: market feeds publish the m/m line for these US releases, so
    # a MoM/YoY collision was the MoM row leaking into the YoY metric.
    return 'mom' in str(sibling.get('key')).split('_') and 'yoy' in str(metric.get('key')).split('_')


def _copied_fields(metric, siblings):
    fields = []
    for field in FIELDS:
        value = clean(metric.get(field))
        if value is None:
            continue
        if field == 'actual' and metric.get('source_tier') not in MARKET_TIERS:
            continue
        for sibling in siblings:
            if clean(sibling.get(field)) != value:
                continue
            if metric_identity_compatible(metric, {'title': _sibling_title(sibling)}):
                continue
            if not _owns_value_over(sibling, metric):
                continue
            fields.append((field, sibling.get('key')))
            break
    return fields


def quarantine_cross_metric_copies(calendar, now_iso=None):
    """Clear copied values in place; return a list of audit rows."""
    audit = []
    for event in calendar.get('events') or []:
        metrics = [m for m in (event.get('market_metrics') or [])
                   if isinstance(m, dict) and m.get('key')
                   and m.get('metric_type') != 'market_probability_snapshot']
        for metric in metrics:
            if not _legacy_generic(metric):
                continue
            siblings = [s for s in metrics if s is not metric]
            copied = _copied_fields(metric, siblings)
            if not copied:
                continue
            store = metric.setdefault('quarantined_values', {})
            for field, source_key in copied:
                store[field] = {'value': metric.get(field), 'copied_from': source_key,
                                'reason': REASON, 'quarantined_kst': now_iso}
                metric[field] = None
                audit.append({'title': event.get('title'), 'datetime_kst': event.get('datetime_kst'),
                              'key': metric['key'], 'field': field,
                              'value': store[field]['value'], 'copied_from': source_key})
                if field == 'actual':
                    for k in PROVENANCE:
                        metric.pop(k, None)
                    metric['market_value_status'] = 'QUARANTINED'
                    # Compact clients mirror the primary metric; keep them consistent.
                    if clean(event.get('actual')) == store[field]['value'] and \
                            event.get('source_tier') in MARKET_TIERS and metrics and metrics[0] is metric:
                        event['actual'] = None
            if 'actual' not in dict(copied) and clean(metric.get('actual')) is None:
                metric['market_value_status'] = 'QUARANTINED'
    return audit

