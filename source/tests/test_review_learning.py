"""Regression cases found in the v0.7.1 execution/learning review."""
import asyncio
import copy
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pandas as pd
import numpy as np
import pytest

from engine import adaptive, agents, research
from engine.adaptive import METHODS, SCHEMA, decision, update_controller
from engine.store import Store
from engine.training import BackgroundTraining, reset_broken_pool


KEY = 'Binance:BTCUSDT:spot:intraday'


def candidate(version='baseline', *, policy=False, coefficients=True):
    result = dict(schema=SCHEMA, version=version, qualified=False, candle_time=100,
                  trained_at=10, samples=100, evaluation_samples=30,
                  families={m: dict(count=20, mean_r=.3, net_r=6, wins=12, drawdown_r=2) for m in METHODS},
                  qualification=dict(count=20, net_r=2, drawdown_r=2),
                  baseline=dict(count=20, net_r=1, drawdown_r=2))
    if coefficients:
        result.update(coefficients=[0.] * 19, intercept=2.)
    if policy:
        result['policy'] = dict(methods=['breakout'], minimum_score=.65)
    return result


def momentum():
    return dict(method='momentum', side='long', price=100, stop=98, target=104,
                candle_time=0, features=[0.] * 19, reason='Fixture')


def baseline():
    return dict(schema=SCHEMA, latest=candidate(), bootstrap_done=True,
                history=[], promotions=0, status='statistical')


@pytest.mark.parametrize('coefficients', [True, False])
def test_experiment_cannot_replace_live_statistical_baseline(coefficients):
    old = baseline()
    experiment = candidate('ai', policy=True, coefficients=coefficients)
    state = agents.queue_experiment(old, experiment, now=30)
    assert decision(old, [momentum()], [], 40)['method'] == 'momentum'
    assert decision(state, [momentum()], [], 40)['method'] == 'momentum'
    assert state['latest'] == old['latest']
    assert state['bootstrap_done'] == old['bootstrap_done']
    assert 'champion' not in state
    if coefficients:
        assert state['pending'] == experiment and state['pending_since'] == 30
    else:
        assert state == old


def test_first_experiment_cannot_become_live_before_normal_scan():
    state = agents.queue_experiment({}, candidate('ai', policy=True), now=30)
    assert 'latest' not in state and 'champion' not in state
    assert 'bootstrap_done' not in state
    assert decision(state, [momentum()], [], 40) is None
    normal = candidate('normal')
    normal['qualified'] = True
    state = update_controller(state, normal, now=50)
    assert state['champion']['version'] == 'normal'
    assert state['pending']['version'] == 'ai'


def test_experiment_queue_is_bounded_deduplicated_and_preserves_active_versions():
    old = baseline()
    old['champion'] = candidate('champion')
    saved = copy.deepcopy(old)
    state = old
    for i in range(6):
        state = agents.queue_experiment(state, candidate(f'ai-{i}', policy=True), now=30+i)
    assert state['latest'] == saved['latest'] and state['champion'] == saved['champion']
    assert old == saved
    assert state['pending']['version'] == 'ai-0'
    assert [c['version'] for c in state['queue']] == ['ai-3', 'ai-4', 'ai-5']
    assert agents.queue_experiment(state, candidate('ai-4', policy=True), now=99) == state


def test_migration_quarantines_only_unapproved_experimental_fallback(monkeypatch):
    monkeypatch.setattr(agents.time, 'time', lambda: 400)
    ai = candidate('ai', policy=True)
    controllers = dict(unapproved=dict(latest=ai, pending=copy.deepcopy(ai), pending_since=10,
                                       forward={'champion': {'count': 19}}, queue=[candidate('queued', policy=True)]),
                       promoted=dict(latest=copy.deepcopy(ai), champion=copy.deepcopy(ai)),
                       normal=baseline())
    saved = copy.deepcopy(controllers)
    assert agents.quarantine_experimental_latest(controllers) == 1
    assert 'latest' not in controllers['unapproved']
    assert controllers['unapproved']['pending'] == saved['unapproved']['pending']
    assert controllers['unapproved']['queue'] == saved['unapproved']['queue']
    assert controllers['unapproved']['pending_since'] == 400
    assert 'forward' not in controllers['unapproved']
    assert controllers['promoted'] == saved['promoted'] and controllers['normal'] == saved['normal']
    assert agents.quarantine_experimental_latest(controllers) == 0


def fake_ai_engine(tmp_path):
    proposal = dict(strategy='intraday', venue='Binance', symbol='BTCUSDT', market='spot',
                    methods=['breakout'], minimum_score=.65, hypothesis='Review regression experiment')
    e = SimpleNamespace(ai_cycle_lock=asyncio.Lock(), lock=asyncio.Lock(), news=[], controllers={KEY: baseline()},
                        store=Store(tmp_path), mode='PAPER', state=dict(session_id='session', running=True), closing=False,
                        settings=SimpleNamespace(local_ai_enabled=True, local_ai_research=True, allowlist=['BTCUSDT']),
                        audit=lambda *a: None, feedback=lambda key: [], candles=lambda *a: [dict(time=100)],
                        learning_pool=ThreadPoolExecutor(max_workers=1))
    e.local_ai = SimpleNamespace(disabled=False, infer=lambda payload: dict(summary='Fixture', events=[], experiment=proposal))
    return e


def test_actual_ai_cycle_preserves_baseline_and_queues_experiment(tmp_path, monkeypatch):
    e = fake_ai_engine(tmp_path)
    old = copy.deepcopy(e.controllers)
    monkeypatch.setattr(agents, 'train_candidate', lambda *a: candidate('ai', policy=True))
    try:
        asyncio.run(agents.run_cycle(e))
        assert e.controllers[KEY]['latest'] == old[KEY]['latest']
        assert e.controllers[KEY]['pending']['version'] == 'ai'
        assert decision(e.controllers[KEY], [momentum()], [], 40)['method'] == 'momentum'
        assert e.store.get('local_ai_experiments')[-1]['status'] == 'forward_queue'
        assert e.store.get('adaptive_controllers')[KEY] == e.controllers[KEY]
    finally:
        e.learning_pool.shutdown(wait=True)
        e.store.db.close()


async def until(predicate, timeout=15):
    async def wait():
        while not predicate():
            await asyncio.sleep(.005)
    await asyncio.wait_for(wait(), timeout)


@pytest.mark.parametrize('stage', ['inference', 'training'])
@pytest.mark.parametrize('change', ['pause', 'mode', 'session', 'disabled', 'closing', 'research'])
def test_ai_result_lifecycle_is_rechecked_across_awaits(tmp_path, monkeypatch, stage, change):
    async def scenario():
        e = fake_ai_engine(tmp_path)
        old = copy.deepcopy(e.controllers)
        entered, release = threading.Event(), threading.Event()
        infer = e.local_ai.infer
        def blocked_infer(payload):
            if stage == 'inference':
                entered.set(); release.wait(5)
            return infer(payload)
        def train(*args):
            if stage == 'training':
                entered.set(); release.wait(5)
            return candidate('ai', policy=True)
        e.local_ai.infer = blocked_infer
        monkeypatch.setattr(agents, 'train_candidate', train)
        task = asyncio.create_task(agents.run_cycle(e))
        try:
            await until(entered.is_set)
            async with e.lock:
                if change == 'pause': e.state['running'] = False
                if change == 'mode': e.mode = 'DEMO'
                if change == 'session': e.state['session_id'] = 'new-session'
                if change == 'disabled': e.settings.local_ai_enabled = False
                if change == 'closing': e.closing = True
                if change == 'research': e.settings.local_ai_research = False
            release.set()
            await asyncio.wait_for(task, 5)
            assert e.controllers == old
            experiments = e.store.get('local_ai_experiments', [])
            if stage == 'training':
                assert experiments[-1]['status'] == 'cancelled'
            else:
                assert experiments == []
        finally:
            release.set()
            if not task.done(): task.cancel()
            e.learning_pool.shutdown(wait=True)
            e.store.db.close()
    asyncio.run(scenario())


def crashing_trainer(rows, *args):
    if rows[-1]['time'] == 100:
        os._exit(17)
    result = candidate('recovered')
    result['candle_time'] = rows[-1]['time']
    return result


def test_real_worker_process_crash_recovers_without_app_restart():
    async def scenario():
        e = SimpleNamespace(mode='PAPER', closing=False, state=dict(session_id='session', running=True),
                            enabled=dict(intraday=True), settings=SimpleNamespace(allowlist=['BTCUSDT', 'ETHUSDT']),
                            analysis_cache={}, controllers={}, controllers_dirty=False, lock=asyncio.Lock(),
                            learning_pool=None, feedback=lambda key: [], audit=lambda *a: None)
        q = BackgroundTraining(e, crashing_trainer)
        assert q.submit('PAPER', 'session', KEY, [dict(time=100)], 'intraday', 'spot')
        task = asyncio.create_task(q.run())
        try:
            await until(lambda: q.failed == 1)
            assert q.last_error == 'BrokenProcessPool' and e.learning_pool is None
            key2 = KEY.replace('BTCUSDT', 'ETHUSDT')
            assert q.submit('PAPER', 'session', key2, [dict(time=200)], 'intraday', 'spot')
            await until(lambda: q.completed == 1)
            assert e.controllers[key2]['latest']['version'] == 'recovered'
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
            if e.learning_pool: e.learning_pool.shutdown(wait=True)
    asyncio.run(scenario())


def test_old_broken_pool_cannot_detach_new_replacement():
    class Pool:
        def shutdown(self, **kwargs): self.stopped = True
    old, new = Pool(), Pool()
    engine = SimpleNamespace(learning_pool=new)
    reset_broken_pool(engine, old)
    assert engine.learning_pool is new and old.stopped


def backtest_fixture(monkeypatch, *, side=1, count=4, strategy='intraday'):
    step = 900 if strategy == 'intraday' else 14400
    rows = [dict(time=(10000+i)*step, open=100., high=100.5, low=99.5, close=100.,
                 volume=100., signal=side if i == 0 else 0, atr=1.,
                 momentum=0., volatility=0., volume_ratio=1., trend_strength=.01) for i in range(count)]
    monkeypatch.setattr(research, 'load_history', lambda *a: (rows, [], 'PUBLIC', None))
    monkeypatch.setattr(research, 'features', lambda rows, strategy: pd.DataFrame(rows))
    params = dict(strategy=strategy, market='futures', symbol='BTCUSDT', venue='Binance', months=36,
                  fee_bps=0, slippage_bps=0)
    return rows, params


@pytest.mark.parametrize('side', [1, -1])
def test_backtest_entry_bar_stop_is_not_ignored(tmp_path, monkeypatch, side):
    rows, params = backtest_fixture(monkeypatch, side=side)
    if side == 1:
        rows[1].update(low=97.)
        rows[2].update(high=105.)
    else:
        rows[1].update(high=103.)
        rows[2].update(low=95.)
    result = research.run_backtest(params, tmp_path)
    assert result['execution_model'] == 'bar-causal-v2'
    trade = result['trades'][0]
    assert trade['reason'] == 'Stop' and trade['time'] == trade['entry_time'] == rows[1]['time']
    assert trade['net'] == pytest.approx(-50)


@pytest.mark.parametrize('side', [1, -1])
def test_backtest_same_entry_bar_stop_and_target_is_stop_first(tmp_path, monkeypatch, side):
    rows, params = backtest_fixture(monkeypatch, side=side)
    rows[1].update(low=95., high=105.)
    result = research.run_backtest(params, tmp_path)
    assert result['trades'][0]['reason'] == 'Stop' and result['trades'][0]['net'] < 0


def test_backtest_cannot_reopen_at_past_open_after_intrabar_exit(tmp_path, monkeypatch):
    rows, params = backtest_fixture(monkeypatch, count=5)
    rows[1]['signal'] = 1
    rows[2]['low'] = 97.
    result = research.run_backtest(params, tmp_path)
    assert len(result['trades']) == 1
    assert result['trades'][0]['time'] == rows[2]['time']


@pytest.mark.parametrize('strategy,horizon', [('intraday',16), ('swing',42)])
def test_backtest_holding_limit_counts_entry_bar(tmp_path, monkeypatch, strategy, horizon):
    rows, params = backtest_fixture(monkeypatch, count=horizon+4, strategy=strategy)
    result = research.run_backtest(params, tmp_path)
    assert result['trades'][0]['time'] == rows[horizon]['time']
    assert result['trades'][0]['reason'] == 'Süre / dönem sonu'


def adaptive_rows(count=100, strategy='intraday', side=1):
    step = 900 if strategy == 'intraday' else 14400
    return [dict(time=i*step, open=100., high=100.5, low=99.5, close=100., volume=100.,
                 signal=side if i == count-1 else 0, atr=1., fast=101., slow=99.,
                 momentum=0., volatility=0., volume_ratio=1., trend_strength=.01,
                 z=0., rsi=50., hist=0.) for i in range(count)]


@pytest.mark.parametrize('strategy', ['intraday','swing'])
@pytest.mark.parametrize('side', [1,-1])
def test_recent_raw_gap_vetoes_options_and_current_analysis(monkeypatch, strategy, side):
    rows = adaptive_rows(strategy=strategy, side=side)
    def frame(data, *args):
        df = pd.DataFrame(data)
        return df, {'momentum': df.signal.to_numpy()}
    monkeypatch.setattr(adaptive, 'frame', frame)
    monkeypatch.setattr(research, 'features', lambda data, strategy: pd.DataFrame(data))
    before = adaptive.options(rows, strategy, 'futures')
    assert len(before) == 1
    assert research.analyze_candles(rows, strategy, 'futures')[0] is not None
    gapped = rows[:-2] + rows[-1:]
    assert adaptive.options(gapped, strategy, 'futures') == []
    signal, context = research.analyze_candles(gapped, strategy, 'futures')
    assert signal is None and context['regime'] == 'unavailable'
    assert context['data_quality'] == 'gap'
    assert adaptive.options(rows, strategy, 'futures') == before


@pytest.mark.parametrize('strategy', ['intraday','swing'])
def test_recent_continuity_is_bounded_and_accepts_short_contiguous_inputs(strategy):
    rows = adaptive_rows(strategy=strategy)
    assert research.recent_contiguous(rows[:10], strategy)
    assert research.recent_contiguous(rows[0:2] + rows[3:], strategy)  # Gap precedes the last80 raw bars.
    assert not research.recent_contiguous([], strategy)


@pytest.mark.parametrize('side', [1,-1])
@pytest.mark.parametrize('gap_index', [1,5])
def test_adaptive_labels_discard_entry_and_held_bar_gaps(monkeypatch, side, gap_index):
    rows = adaptive_rows(count=22, side=side)
    def frame(data, *args):
        signals = np.zeros(len(data), dtype=int)
        signals[0] = side
        return pd.DataFrame(data), {'momentum': signals}
    monkeypatch.setattr(adaptive, 'frame', frame)
    complete = adaptive.dataset(rows, 'intraday', 'futures')
    assert len(complete) == 1
    gapped = rows[:gap_index] + rows[gap_index+1:]
    assert adaptive.dataset(gapped, 'intraday', 'futures') == []
    assert adaptive.dataset(rows, 'intraday', 'futures') == complete


def test_gap_after_resolved_label_does_not_invalidate_prior_outcome(monkeypatch):
    rows = adaptive_rows(count=22)
    rows[2]['high'] = 105.
    def frame(data, *args):
        signals = np.zeros(len(data), dtype=int)
        signals[0] = 1
        return pd.DataFrame(data), {'momentum': signals}
    monkeypatch.setattr(adaptive, 'frame', frame)
    complete = adaptive.dataset(rows, 'intraday', 'futures')
    assert len(complete) == 1 and complete[0]['end'] == 3*900
    assert adaptive.dataset(rows[:5]+rows[6:], 'intraday', 'futures') == complete


def test_explicit_news_research_can_run_while_paper_entries_remain_paused(tmp_path,monkeypatch):
    e=fake_ai_engine(tmp_path);e.state['running']=False
    old=copy.deepcopy(e.controllers)
    monkeypatch.setattr(agents,'train_candidate',lambda *a:candidate('ai-paused',policy=True))
    try:
        asyncio.run(agents.run_cycle(e,allow_paused=True))
        assert not e.state['running']
        assert e.controllers[KEY]['latest']==old[KEY]['latest']
        assert e.controllers[KEY]['pending']['version']=='ai-paused'
        assert e.ai_report['summary']=='Fixture'
    finally:e.learning_pool.shutdown(wait=True);e.store.db.close()
