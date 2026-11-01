import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import add_observatory_equities as equities


class CryptoObservationTest(unittest.TestCase):
    def test_weekend_candles_use_utc_and_current_quote_keeps_timestamp(self):
        utc = ZoneInfo('UTC')
        now = datetime(2026, 10, 11, 23, 15, tzinfo=utc)
        quote = int(now.timestamp())
        payload = {'chart': {'result': [{
            'meta': {'regularMarketPrice': 101, 'regularMarketTime': quote},
            'timestamp': [int(datetime(2026, 10, 10, tzinfo=utc).timestamp()), int(datetime(2026, 10, 11, tzinfo=utc).timestamp())],
            'indicators': {'quote': [{'close': [100, 100.5]}]},
        }]}}
        with patch.object(equities, 'get_json', return_value=payload):
            rows, snapshot = equities.crypto_observation('BTC-USD', now)
        self.assertEqual([r['date'] for r in rows], ['2026-10-10', '2026-10-11'])
        self.assertEqual(rows[-1]['value'], 101)
        self.assertEqual(rows[-1]['session_status'], 'IN_PROGRESS')
        self.assertEqual(snapshot['quote_as_of_kst'], '2026-10-12T08:15:00+09:00')
        self.assertEqual(snapshot['status'], 'LIVE')

    def test_provider_failure_preserves_last_verified_values_and_marks_stale(self):
        data = {'series': {'BTCUSD': [{'date': '2026-10-10', 'value': 100}]},
                'latest': {'BTCUSD': 100}, 'crypto_market': {'BTCUSD': {'price': 100}}}
        with patch.object(equities, 'coingecko_spot_observations', side_effect=RuntimeError('source unavailable')), \
             patch.object(equities, 'crypto_observation', side_effect=RuntimeError('source unavailable')):
            equities.enrich_crypto(data)
        self.assertEqual(data['latest']['BTCUSD'], 100)
        self.assertEqual(data['series']['BTCUSD'][0]['value'], 100)
        self.assertEqual(data['crypto_market']['BTCUSD']['status'], 'STALE')
        self.assertEqual(data['crypto_market']['ETHUSD']['status'], 'UNAVAILABLE')

    def test_full_rebuild_retains_weekend_observation_until_refresh(self):
        previous={'series':{'BTCUSD':[{'date':'2026-10-11','value':101}]},'crypto_market':{'BTCUSD':{'status':'LIVE','quote_as_of_kst':'2026-10-12T08:15:00+09:00'}}}
        current={'series':{'SP500':[{'date':'2026-10-09','value':100}]}}
        equities.retain_crypto_observations(current,previous)
        self.assertEqual(current['series']['BTCUSD'][0]['date'],'2026-10-11')
        self.assertEqual(current['latest']['BTCUSD'],101)
        self.assertEqual(current['crypto_market']['BTCUSD']['status'],'STALE')
        self.assertEqual(previous['crypto_market']['BTCUSD']['status'],'LIVE')

    def test_quote_without_provider_timestamp_is_rejected(self):
        with patch.object(equities, 'get_json', return_value={'chart': {'result': [{'meta': {'regularMarketPrice': 101}}]}}):
            with self.assertRaisesRegex(ValueError, 'METADATA_MISSING'):
                equities.crypto_observation('ETH-USD')


    def test_coingecko_one_request_two_quotes_preserves_provider_timestamp(self):
        utc = ZoneInfo('UTC')
        now = datetime(2026, 11, 1, 9, 0, tzinfo=utc)
        payload = {
            'bitcoin': {'usd': 77700.5, 'last_updated_at': int(now.timestamp()) - 20},
            'ethereum': {'usd': 2200.25, 'last_updated_at': int(now.timestamp()) - 15},
        }
        with patch.object(equities, 'get_json', return_value=payload) as getter:
            observations = equities.coingecko_spot_observations(now)
        self.assertEqual(getter.call_count, 1)
        self.assertIn('include_last_updated_at=true', getter.call_args.args[0])
        self.assertEqual(set(observations), {'BTCUSD', 'ETHUSD'})
        rows, snapshot = observations['BTCUSD']
        self.assertEqual(rows[0]['observation_type'], 'SPOT_SNAPSHOT')
        self.assertEqual(rows[0]['session_status'], 'IN_PROGRESS')
        self.assertEqual(snapshot['price'], 77700.5)
        self.assertEqual(snapshot['quote_as_of_kst'], '2026-11-01T17:59:40+09:00')
        self.assertEqual(snapshot['quote_age_seconds'], 20)
        self.assertEqual(snapshot['status'], 'LIVE')

    def test_coingecko_primary_keeps_historical_daily_rows_when_yahoo_unavailable(self):
        utc = ZoneInfo('UTC')
        now = datetime(2026, 11, 1, 9, 0, tzinfo=utc)
        payload = {
            'bitcoin': {'usd': 77700.5, 'last_updated_at': int(now.timestamp()) - 20},
            'ethereum': {'usd': 2200.25, 'last_updated_at': int(now.timestamp()) - 15},
        }
        with patch.object(equities, 'get_json', return_value=payload):
            quotes = equities.coingecko_spot_observations(now)
        data = {
            'series': {
                'BTCUSD': [{'date': '2026-10-30', 'value': 75000, 'session_status': 'COMPLETED', 'date_basis': 'UTC'}],
                'ETHUSD': [{'date': '2026-10-30', 'value': 2100, 'session_status': 'COMPLETED', 'date_basis': 'UTC'}],
            },
            'latest': {}, 'crypto_market': {},
        }
        with patch.object(equities, 'coingecko_spot_observations', return_value=quotes), \
             patch.object(equities, 'crypto_observation', side_effect=RuntimeError('Yahoo history unavailable')):
            equities.enrich_crypto(data)
        self.assertEqual(data['series']['BTCUSD'][0]['value'], 75000)
        self.assertEqual(data['series']['BTCUSD'][0]['session_status'], 'COMPLETED')
        self.assertEqual(data['latest']['BTCUSD'], 77700.5)
        self.assertEqual(data['latest']['ETHUSD'], 2200.25)
        self.assertIn('CoinGecko', data['crypto_market']['BTCUSD']['source'])

    def test_coingecko_missing_symbol_uses_yahoo_for_that_symbol_only(self):
        utc = ZoneInfo('UTC')
        now = datetime(2026, 11, 1, 9, 0, tzinfo=utc)
        with patch.object(equities, 'get_json', return_value={
            'bitcoin': {'usd': 77700, 'last_updated_at': int(now.timestamp())},
            'ethereum': {'usd': 2200},
        }):
            quotes = equities.coingecko_spot_observations(now)
        self.assertEqual(set(quotes), {'BTCUSD'})
        yahoo_row = [{'date': '2026-11-01', 'value': 2199}]
        yahoo_snapshot = {'source': 'Yahoo Finance', 'price': 2199, 'status': 'LIVE',
                          'quote_as_of_kst': '2026-11-01T18:00:00+09:00'}
        data = {'series': {}, 'latest': {}, 'crypto_market': {}}
        def yahoo_stub(symbol):
            if symbol == 'BTC-USD':
                raise RuntimeError('Yahoo daily history unavailable')
            return yahoo_row, yahoo_snapshot
        with patch.object(equities, 'coingecko_spot_observations', return_value=quotes), \
             patch.object(equities, 'crypto_observation', side_effect=yahoo_stub) as fallback:
            equities.enrich_crypto(data)
        self.assertEqual(fallback.call_count, 2)
        self.assertEqual([call.args[0] for call in fallback.call_args_list], ['BTC-USD', 'ETH-USD'])
        self.assertEqual(data['latest']['BTCUSD'], 77700)
        self.assertEqual(data['latest']['ETHUSD'], 2199)

    def test_coingecko_quote_preserves_yahoo_completed_history(self):
        utc = ZoneInfo('UTC')
        now = datetime(2026, 11, 1, 9, 0, tzinfo=utc)
        payload = {
            'bitcoin': {'usd': 77700, 'last_updated_at': int(now.timestamp())},
            'ethereum': {'usd': 2200, 'last_updated_at': int(now.timestamp())},
        }
        with patch.object(equities, 'get_json', return_value=payload):
            quotes = equities.coingecko_spot_observations(now)
        daily = [
            {'date': '2026-10-31', 'value': 74000, 'session_status': 'COMPLETED', 'date_basis': 'UTC'},
            {'date': '2026-11-01', 'value': 76000, 'session_status': 'IN_PROGRESS', 'date_basis': 'UTC'},
        ]
        data = {'series': {'BTCUSD': [{'date': '2026-10-31', 'value': 73000, 'session_status': 'IN_PROGRESS'}]},
                'latest': {}, 'crypto_market': {}}
        with patch.object(equities, 'coingecko_spot_observations', return_value=quotes), \
             patch.object(equities, 'crypto_observation', return_value=(daily, {'status': 'LIVE'})):
            equities.enrich_crypto(data)
        self.assertEqual(data['series']['BTCUSD'][0]['value'], 74000)
        self.assertEqual(data['series']['BTCUSD'][0]['session_status'], 'COMPLETED')
        self.assertEqual(data['series']['BTCUSD'][-1]['value'], 77700)
        self.assertEqual(data['series']['BTCUSD'][-1]['observation_type'], 'SPOT_SNAPSHOT')

    def test_coingecko_rejects_missing_stale_future_or_invalid_timestamp(self):
        utc = ZoneInfo('UTC')
        now = datetime(2026, 11, 1, 9, 0, tzinfo=utc)
        payload = {
            'bitcoin': {'usd': 77700, 'last_updated_at': int(now.timestamp()) - 3601},
            'ethereum': {'usd': 2200, 'last_updated_at': int(now.timestamp()) + 301},
        }
        with patch.object(equities, 'get_json', return_value=payload):
            self.assertEqual(equities.coingecko_spot_observations(now), {})
        payload['bitcoin'] = {'usd': 77700}
        payload['ethereum'] = {'usd': float('nan'), 'last_updated_at': int(now.timestamp())}
        with patch.object(equities, 'get_json', return_value=payload):
            self.assertEqual(equities.coingecko_spot_observations(now), {})


if __name__ == '__main__':
    unittest.main()
