import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import pytest
import engine.core as core
from engine.core import Engine


def setup(e,monkeypatch):
    e.state['running']=True
    e.state['markets']=[dict(venue='Binance',symbol='SOLUSDT',market='futures',price=100,bid=99.99,ask=100.01,volume=10000000,observed=time.time())]
    monkeypatch.setattr(core,'analyze_candles',lambda *args:(None,dict(regime='range')))
    monkeypatch.setattr(core,'options',lambda *args:[])
    return [dict(time=int(time.time()//900)*900-900,open=100,high=101,low=99,close=100,volume=100)]


@pytest.mark.parametrize('change',['disable','replace_session','pause'])
def test_pending_scan_cannot_commit_after_lifecycle_change(tmp_path,monkeypatch,change):
    e=Engine(tmp_path)
    rows=setup(e,monkeypatch)
    entered=threading.Event();release=threading.Event()
    def candles(*args):
        entered.set();release.wait(3)
        return rows
    monkeypatch.setattr(e,'candles',candles)
    async def scenario():
        task=asyncio.create_task(e.scan_one('PAPER','Binance','SOLUSDT','futures','intraday'))
        assert await asyncio.to_thread(entered.wait,2)
        if change=='disable':e.enabled['intraday']=False
        elif change=='pause':e.state['running']=False
        else:e.state['session_id']='replacement'
        release.set()
        await task
    asyncio.run(scenario())
    assert not e.state['decisions'] and not e.controllers and not e.state.get('adaptive_trials')


def test_live_feedback_is_refreshed_after_awaited_training(tmp_path,monkeypatch):
    e=Engine(tmp_path)
    rows=setup(e,monkeypatch)
    monkeypatch.setattr(e,'candles',lambda *args:rows)
    entered=threading.Event();release=threading.Event();seen=[]
    def train(*args):
        entered.set();release.wait(3)
        return {'schema':core.SCHEMA,'candle_time':rows[-1]['time']}
    monkeypatch.setattr(core,'train_candidate',train)
    monkeypatch.setattr('engine.training.update_controller',lambda old,candidate:dict(latest=candidate,schema=core.SCHEMA))
    monkeypatch.setattr(core,'consider_promotion',lambda *args:None)
    monkeypatch.setattr(core,'consider_rollback',lambda controller,actual:seen.extend(actual))
    monkeypatch.setattr(core,'register_trials',lambda *args:None)
    monkeypatch.setattr(core,'decision',lambda controller,choices,actual:None)
    monkeypatch.setattr(core,'public_state',lambda *args:{})
    with ThreadPoolExecutor(max_workers=1) as pool:
        e.learning_pool=pool
        e.training.trainer=train
        async def scenario():
            worker=asyncio.create_task(e.training.run())
            await e.scan_one('PAPER','Binance','SOLUSDT','futures','intraday')
            assert await asyncio.to_thread(entered.wait,2)
            e.store.set('adaptive_feedback',[dict(id='new-loss',venue='Binance',symbol='SOLUSDT',market='futures',strategy='intraday',r=-2)])
            release.set()
            async def finished():
                while e.training.current or not e.training.completed:await asyncio.sleep(.01)
            await asyncio.wait_for(finished(),3)
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):await worker
        asyncio.run(scenario())
    assert [r['id'] for r in seen]==['new-loss']
