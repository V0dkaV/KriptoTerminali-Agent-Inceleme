import math
from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from engine.history import HistoryService, calendar_start, INTERVALS
from engine.server import create_app

NOW = datetime(2026, 10, 15, 12, 34, tzinfo=timezone.utc).timestamp()


def bar(stamp, step):
    price = 100 + stamp / 86400 * .01
    return dict(time=stamp, open=price, high=price + 2, low=price - 2, close=price + 1, volume=2)


class FakeExchange:
    calls = []
    missing = set()
    fail = False
    oldest_first = False

    def __init__(self, venue):
        self.venue = venue

    def candles(self, symbol, interval, market, limit, start, end):
        self.calls.append(dict(interval=interval, start=start, end=end))
        if self.fail:
            raise OSError('secret request details must never appear')
        step = INTERVALS[interval]
        rows = [bar(t, step) for t in range(math.ceil(start / step) * step, int(end // step + 1) * step, step) if t not in self.missing]
        # Bybit-like newest-first, inclusive endpoint and duplicated exchange row.
        rows = rows[:limit] if self.oldest_first else list(reversed(rows[-limit:]))
        return rows + rows[:1]


@pytest.fixture
def service(tmp_path):
    FakeExchange.calls, FakeExchange.missing, FakeExchange.fail, FakeExchange.oldest_first = [], set(), False, False
    return HistoryService(tmp_path, FakeExchange, lambda: NOW)


def test_calendar_months_are_not_180_or_365_day_shortcuts():
    march = datetime(2024, 3, 31, 12, tzinfo=timezone.utc).timestamp()
    assert datetime.fromtimestamp(calendar_start(march, 1), timezone.utc) == datetime(2024, 2, 29, 12, tzinfo=timezone.utc)
    assert datetime.fromtimestamp(calendar_start(NOW, 6), timezone.utc) == datetime(2026, 4, 15, 12, 34, tzinfo=timezone.utc)


def test_one_year_history_paginates_closed_deduplicated_bounds_and_warmup(service):
    result = service.get(months=12, interval='4h')
    rows, coverage = result['rows'], result['coverage']
    assert coverage['status'] == 'complete'
    assert coverage['actual'] == coverage['expected'] > 2000
    assert len(rows) == len({r['time'] for r in rows})
    assert rows[0]['time'] >= result['range']['requested_start']
    assert rows[-1]['time'] + 14400 <= NOW
    assert coverage['warmup_actual'] == 200
    assert len([c for c in FakeExchange.calls if c['interval'] == '4h']) == 3
    assert result['summary']['daily_context']['trend'] == 'up'
    assert result['summary']['warmup_sufficient']
    assert result['summary']['max_drawdown_pct'] == 0
    assert result['summary']['volume_total'] == len(rows) * 2


def test_cache_survives_new_instance_and_only_requests_missing_new_bar(service, tmp_path):
    initial = service.get(interval='1d')
    calls = len(FakeExchange.calls)
    reopened = HistoryService(tmp_path, FakeExchange, lambda: NOW)
    assert reopened.get()['rows'] == initial['rows']
    assert len(FakeExchange.calls) == calls
    later = HistoryService(tmp_path, FakeExchange, lambda: NOW + 86400)
    updated = later.get()
    assert len(FakeExchange.calls) == calls + 1
    request = FakeExchange.calls[-1]
    assert request['end'] - request['start'] < 86400
    assert updated['coverage']['status'] == 'complete'


def test_oldest_first_exchange_also_covers_all_pages(service):
    FakeExchange.oldest_first = True
    result = service.get(interval='4h', months=12)
    assert result['coverage']['status'] == 'complete'
    assert len([c for c in FakeExchange.calls if c['interval'] == '4h']) == 3
    assert all(c['end'] - c['start'] < INTERVALS[c['interval']] * 1000 for c in FakeExchange.calls)


def test_holes_remain_partial_never_interpolated_and_do_not_retry_immediately(service):
    absent = int(NOW // 86400 - 10) * 86400
    FakeExchange.missing = {absent}
    result = service.get()
    assert result['coverage']['status'] == 'partial'
    assert result['coverage']['missing'] == 1
    assert result['coverage']['gaps'] == [dict(start=absent, end=absent, missing=1)]
    assert absent not in {r['time'] for r in result['rows']}
    assert result['summary']['daily_context']['trend'] == 'insufficient'
    calls = len(FakeExchange.calls)
    assert service.get()['coverage']['status'] == 'partial'
    assert len(FakeExchange.calls) == calls


def test_network_failure_has_no_demo_fallback_or_secret_error(service):
    FakeExchange.fail = True
    result = service.get()
    assert result['rows'] == [] and result['source'] == 'PAPER'
    assert result['coverage']['status'] == 'unavailable' and result['stale']
    assert result['summary']['return_pct'] is None
    assert 'secret' not in str(result)


def test_warmup_is_not_counted_as_visible_performance(service):
    result = service.get()
    rows = result['rows']
    assert result['summary']['return_pct'] == pytest.approx((rows[-1]['close'] / rows[0]['open'] - 1) * 100)
    assert result['coverage']['daily_actual'] == len(rows) + 200
    assert len(list(service.directory.glob('*.parquet'))) == 1


def test_demo_is_explicit_and_does_not_pollute_real_cache(service):
    result = service.get(source='DEMO')
    assert result['source'] == 'DEMO' and result['coverage']['status'] == 'complete'
    assert not FakeExchange.calls
    assert 'DEMO' in result['summary']['limitations'][0]
    assert service.latest_summaries() == []
    assert not list(service.directory.glob('*.parquet'))


@pytest.mark.parametrize('kwargs', [dict(symbol='../BTCUSDT'), dict(months=7), dict(interval='15m'), dict(venue='Other'), dict(market='margin')])
def test_history_input_is_bounded(service, kwargs):
    with pytest.raises(ValueError):
        service.get(**kwargs)
    assert not FakeExchange.calls


def test_route_authenticated_validated_and_modes_are_explicit(tmp_path):
    app = create_app(tmp_path, 'history-token')
    client = TestClient(app)
    headers = {'Authorization': 'Bearer history-token'}
    assert client.get('/history').status_code == 401
    assert client.get('/history?months=3', headers=headers).status_code == 400
    assert client.get('/history?symbol=../BTCUSDT', headers=headers).status_code == 400
    app.state.engine.mode = 'DEMO'
    response = client.get('/history?months=12&interval=4h', headers=headers)
    assert response.status_code == 200
    assert response.json()['source'] == 'DEMO'


def test_corrupt_cache_is_refetched_not_silently_trusted(service):
    path = service.directory / 'Binance-spot-BTCUSDT-1d.parquet'
    path.write_bytes(b'corrupt parquet')
    result = service.get()
    assert result['coverage']['status'] == 'complete'
    assert len(pd.read_parquet(path)) > len(result['rows'])


def test_recent_summary_context_is_real_bounded_and_detached(service):
    for symbol in ('BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT'):
        service.get(symbol=symbol)
    recent = service.latest_summaries()
    assert len(recent) == 4 and recent[0]['symbol'] == 'ETHUSDT'
    assert all(r['source'] == 'PAPER' and r['coverage']['status'] == 'complete' for r in recent)
    recent[0]['summary']['trend'] = 'altered'
    assert service.latest_summaries()[0]['summary']['trend'] != 'altered'


def test_missing_warmup_remains_explicit_even_if_visible_range_complete(service):
    start = math.ceil(calendar_start(NOW, 6) / 86400) * 86400
    FakeExchange.missing = set(range(start - 200 * 86400, start, 86400))
    result = service.get()
    assert result['coverage']['status'] == 'complete'
    assert result['coverage']['warmup_actual'] == 0
    assert not result['summary']['warmup_sufficient']
    assert result['summary']['daily_context']['trend'] == 'insufficient'


def test_invalid_and_open_candles_in_cache_cannot_enter_summary(service):
    result = service.get()
    path = service.directory / 'Binance-spot-BTCUSDT-1d.parquet'
    frame = pd.read_parquet(path)
    corrupt = bar(int(NOW // 86400) * 86400, 86400)
    invalid = {**corrupt, 'time': corrupt['time'] - 86400, 'high': -2}
    pd.concat([frame, pd.DataFrame([corrupt, invalid])], ignore_index=True).to_parquet(path, index=False)
    again = service.get()
    assert again['rows'] == result['rows']
    assert all(r['time'] + 86400 <= NOW for r in again['rows'])
