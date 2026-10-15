import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import pytest

import engine.core as core
from engine.core import Engine
from engine.models import Signal


@pytest.fixture
def e(tmp_path,monkeypatch):
    monkeypatch.setenv('KRIPTO_DISABLE_LOCAL_AI','1')
    e=Engine(tmp_path);e.state['running']=True;e.settings.local_ai_enabled=False
    e.settings.allowlist=['SOLUSDT','ETHUSDT'];e.settings.symbol_risk=1.5;e.settings.correlated_risk=2.5
    now=time.time();e.news_sources=[dict(name='test',status='ok',observed=now)]
    e.state['markets']=[dict(venue='Binance',symbol=s,market='futures',price=100.,bid=99.99,ask=100.01,
        mark_price=100.,mark_price_observed=now,volume=10000000.,observed=now,price_observed=now,bid_observed=now,ask_observed=now) for s in e.settings.allowlist]
    rows=[dict(time=int(now//900)*900-900,open=100.,high=101.,low=99.,close=100.,volume=100)]
    monkeypatch.setattr(e,'candles',lambda *args:rows)
    monkeypatch.setattr(core,'analyze_candles',lambda *args:(None,dict(regime='uptrend')))
    choice=dict(method='breakout',side='long',price=100.,stop=99.,target=102.,candle_time=rows[-1]['time'],
                features=[0.]*19,reason='Test approved strategy')
    monkeypatch.setattr(core,'options',lambda *args:[copy.deepcopy(choice)])
    e.test_rows=rows;e.test_choice=choice
    return e


def ready(e,symbol):
    key=f'Binance:{symbol}:futures:intraday'
    e.controllers[key]=dict(schema=core.SCHEMA,latest=dict(schema=core.SCHEMA,candle_time=e.test_rows[-1]['time'],
        version='test-ready',families=dict(breakout=dict(count=20,mean_r=1)),samples=20,evaluation_samples=10))
    return key


async def until(predicate):
    async def wait():
        while not predicate():await asyncio.sleep(.01)
    await asyncio.wait_for(wait(),3)


def test_ready_signal_enters_while_other_context_training_is_blocked(e):
    ready(e,'ETHUSDT')
    entered=threading.Event();release=threading.Event()
    def train(rows,*args):
        entered.set();release.wait(5)
        return dict(schema=core.SCHEMA,candle_time=rows[-1]['time'],qualified=False,families={},version='new')
    with ThreadPoolExecutor(max_workers=1) as pool:
        e.learning_pool=pool;e.training.trainer=train
        async def run():
            worker=asyncio.create_task(e.training.run())
            await e.scan_one('PAPER','Binance','SOLUSDT','futures','intraday',defer=True)
            await until(entered.is_set)
            await asyncio.wait_for(e.scan_one('PAPER','Binance','ETHUSDT','futures','intraday',defer=True),1)
            dispatcher=asyncio.create_task(e.dispatch_entries())
            try:
                await until(lambda:bool(e.state['positions']))
                assert e.state['positions'][0]['symbol']=='ETHUSDT'
                assert e.training.snapshot()['running'] and not release.is_set()
                assert e.state['decisions']['Binance:ETHUSDT:futures:intraday']['block_code']=='opened'
            finally:
                release.set();dispatcher.cancel();worker.cancel()
                await asyncio.gather(dispatcher,worker,return_exceptions=True)
        asyncio.run(run())


def test_slow_network_coin_does_not_delay_prepared_signal(e,monkeypatch):
    ready(e,'ETHUSDT');entered=threading.Event();release=threading.Event()
    def candles(symbol,*args):
        if symbol=='SOLUSDT':entered.set();release.wait(4)
        return e.test_rows
    monkeypatch.setattr(e,'candles',candles)
    async def run():
        slow=asyncio.create_task(e.scan_one('PAPER','Binance','SOLUSDT','futures','intraday',defer=True))
        await until(entered.is_set)
        await e.scan_one('PAPER','Binance','ETHUSDT','futures','intraday',defer=True)
        dispatcher=asyncio.create_task(e.dispatch_entries())
        try:
            await until(lambda:bool(e.state['positions']))
            assert not slow.done() and not release.is_set()
        finally:
            release.set();dispatcher.cancel();await asyncio.gather(slow,dispatcher,return_exceptions=True)
    asyncio.run(run())


def test_fresh_loss_feedback_revokes_previously_approved_signal_before_entry(e):
    ready(e,'ETHUSDT')
    async def run():
        await e.scan_one('PAPER','Binance','ETHUSDT','futures','intraday',defer=True)
        assert any(c['status']=='eligible' for c in e.state['operation_candidates'].values())
        now=time.time()
        e.store.set('adaptive_feedback',[dict(id=str(i),venue='Binance',symbol='ETHUSDT',market='futures',strategy='intraday',
                    method='breakout',r=-2.,closed_at=now-i) for i in range(5)])
        e.operations.dispatch()
    asyncio.run(run())
    assert not e.state['positions']
    assert all(c['status']!='eligible' for c in e.state['operation_candidates'].values())
    assert e.state['decisions']['Binance:ETHUSDT:futures:intraday']['candidate_checks'][0]['code']=='loss_pause'


def test_restart_pending_candidate_waits_for_fresh_analysis(e):
    sig=Signal(strategy='intraday',symbol='ETHUSDT',venue='Binance',market='futures',**e.test_choice)
    e.operations.publish(sig);e.operations.dispatch()
    assert not e.state['positions']
    assert e.state['operation_candidates'][e.operations.identity(sig)]['status']=='eligible'


def test_dispatch_error_does_not_kill_background_entry_task(e,monkeypatch):
    monkeypatch.setattr(e.operations,'dispatch',lambda:(_ for _ in ()).throw(OSError('disk error')))
    async def run():
        task=asyncio.create_task(e.dispatch_entries())
        await until(lambda:bool(e.state['halt']))
        assert not task.done() and not e.state['running']
        task.cancel();await asyncio.gather(task,return_exceptions=True)
    asyncio.run(run())


def test_repeat_analysis_keeps_final_entry_status_and_no_duplicate(e):
    ready(e,'ETHUSDT')
    async def run():
        await e.scan_one('PAPER','Binance','ETHUSDT','futures','intraday')
        await e.scan_one('PAPER','Binance','ETHUSDT','futures','intraday')
    asyncio.run(run())
    assert len(e.state['positions'])==1
    assert e.state['decisions']['Binance:ETHUSDT:futures:intraday']['block_code']=='opened'
    status=e.snapshot()['execution']
    assert sum(r['count'] for r in status['reasons'])==status['analysis']['completed']
    assert status['reasons'][0]['code']=='opened'
