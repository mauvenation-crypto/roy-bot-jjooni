#!/usr/bin/env python3
"""Update only crypto observations; retain all other source timestamps and facts."""
import json
from datetime import datetime
from add_observatory_equities import OBS, KST, CRYPTO_SYMBOLS, enrich_crypto


def main():
    data = json.loads(OBS.read_text(encoding='utf-8'))
    enrich_crypto(data)
    failed=[]
    for key in CRYPTO_SYMBOLS:
        quote = data.get('crypto_market', {}).get(key, {})
        if quote.get('status') != 'LIVE':
            failed.append(key)
            continue
        assert data['series'][key][-1]['value'] == data['latest'][key]
        assert abs(data['latest'][key] - quote['price']) < 0.000001
    data['crypto_enriched_kst'] = datetime.now(KST).isoformat(timespec='seconds')
    OBS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if failed:
        # Persist successful symbols and explicit stale states before failing.
        # The dedicated workflow publishes this partial result, then stays red.
        raise SystemExit('CRYPTO_REFRESH=PARTIAL failed='+','.join(failed))
    print('CRYPTO_REFRESH=PASS', data['crypto_enriched_kst'])


if __name__ == '__main__':
    main()
