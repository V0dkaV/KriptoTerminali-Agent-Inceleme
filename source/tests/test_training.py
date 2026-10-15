import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from engine.adaptive import SCHEMA
from engine.training import BackgroundTraining


KEY = 'Binance:SOLUSDT:futures:intraday'


def fake_engine():
    e = SimpleNamespace(mode='PAPER', closing=False, state=dict(session_id='session', running=True),
                        enabled=dict(intraday=True), settings=SimpleNamespace(allowlist=['SOLUSDT', 'ETHUSDT']),
                        analysis_cache={}, controllers={}, controllers_dirty=False,
                        lock=asyncio.Lock(), learning_pool=ThreadPoolExecutor(max_workers=1), actual=[], audits=[])
    e.feedback = lambda key: list(e.actual)
    e.audit = lambda *args: e.audits.append(args)
    return e


def model(rows, *args):
    return dict(schema=SCHEMA, candle_time=rows[-1]['time'], qualified=False,
                families={}, version=str(rows[-1]['time']))


async def until(predicate):
    async def wait():
        while not predicate():
            await asyncio.sleep(.005)
    await asyncio.wait_for(wait(), 3)


async def stop(task, e):
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    e.learning_pool.shutdown(wait=True)


def submit(q, candle=100, key=KEY):
    return q.submit('PAPER', 'session', key, [dict(time=candle)], 'intraday', 'futures')


def test_submit_nonblocking_deduplicated_bounded_and_newest():
    e = fake_engine()
    try:
        q = BackgroundTraining(e, model, capacity=1)
        assert submit(q)
        assert not submit(q)
        assert submit(q, 200)
        assert not submit(q, 150)
        assert not submit(q, 100, 'Binance:ETHUSDT:futures:intraday')
        assert len(q.pending) == 1
        assert next(iter(q.pending.values())).candle_time == 200
        assert q.snapshot()['queued'] == 1
    finally:
        e.learning_pool.shutdown(wait=True)


def test_worker_does_not_hold_lock_and_callback_reads_fresh_feedback():
    async def scenario():
        e = fake_engine()
        entered = threading.Event()
        release = threading.Event()
        seen = []
        def train(rows, strategy, market, feedback):
            seen.append(('training', feedback))
            entered.set()
            release.wait(3)
            return model(rows)
        async def completed(job):
            assert not e.lock.locked()
            async with e.lock:
                seen.append(('callback', e.feedback(job.key)))
        e.training_completed = completed
        q = BackgroundTraining(e, train)
        assert submit(q)
        task = asyncio.create_task(q.run())
        await until(entered.is_set)
        async with e.lock:
            e.actual = [dict(id='new-loss')]
        assert q.snapshot()['running']
        assert not submit(q)
        release.set()
        await until(lambda: len(seen) == 2)
        assert seen == [('training', []), ('callback', [dict(id='new-loss')])]
        assert e.controllers[KEY]['latest']['candle_time'] == 100
        assert e.controllers_dirty and q.completed == 1
        assert not submit(q)
        await stop(task, e)
    asyncio.run(scenario())


@pytest.mark.parametrize('change', ['pause', 'mode', 'session', 'disable', 'remove', 'closing'])
def test_lifecycle_change_prevents_completed_training_commit(change):
    async def scenario():
        e = fake_engine()
        entered = threading.Event()
        release = threading.Event()
        def train(rows, *args):
            entered.set()
            release.wait(3)
            return model(rows)
        q = BackgroundTraining(e, train)
        submit(q)
        task = asyncio.create_task(q.run())
        await until(entered.is_set)
        if change == 'pause': e.state['running'] = False
        if change == 'mode': e.mode = 'DEMO'
        if change == 'session': e.state['session_id'] = 'replacement'
        if change == 'disable': e.enabled['intraday'] = False
        if change == 'remove': e.settings.allowlist = []
        if change == 'closing': e.closing = True
        release.set()
        await until(lambda: q.current is None)
        assert not e.controllers and not e.controllers_dirty
        assert q.discarded == 1
        if task.done():
            await task
            e.learning_pool.shutdown(wait=True)
        else:
            await stop(task, e)
    asyncio.run(scenario())


def test_newer_closed_candle_discards_old_result_and_uses_latest_feedback():
    async def scenario():
        e = fake_engine()
        entered = threading.Event()
        release = threading.Event()
        seen = []
        def train(rows, strategy, market, feedback):
            seen.append((rows[-1]['time'], feedback))
            if rows[-1]['time'] == 100:
                entered.set()
                release.wait(3)
            return model(rows)
        q = BackgroundTraining(e, train)
        submit(q)
        task = asyncio.create_task(q.run())
        await until(entered.is_set)
        assert submit(q, 200)
        assert submit(q, 300)
        e.analysis_cache[('PAPER', 'Binance', 'SOLUSDT', 'futures', 'intraday')] = (300, None)
        e.actual = [dict(id='latest')]
        release.set()
        await until(lambda: q.completed == 1)
        assert seen == [(100, []), (300, [dict(id='latest')])]
        assert q.discarded == 1
        assert e.controllers[KEY]['latest']['candle_time'] == 300
        await stop(task, e)
    asyncio.run(scenario())


def test_failed_training_survives_and_backoff_is_bounded():
    async def scenario():
        e = fake_engine()
        def train(rows, *args):
            if rows[-1]['time'] == 100:
                raise RuntimeError('sensitive detail must not appear in status')
            return model(rows)
        q = BackgroundTraining(e, train)
        submit(q)
        task = asyncio.create_task(q.run())
        await until(lambda: q.failed == 1)
        assert not submit(q)
        assert q.snapshot()['last_error'] == 'RuntimeError'
        assert e.audits and not task.done()
        assert submit(q, 200, 'Binance:ETHUSDT:futures:intraday')
        await until(lambda: q.completed == 1)
        await stop(task, e)
    asyncio.run(scenario())


@pytest.mark.parametrize('invalid', ['schema', 'candle'])
def test_invalid_candidate_metadata_cannot_commit(invalid):
    async def scenario():
        e = fake_engine()
        def train(rows, *args):
            candidate = model(rows)
            candidate['schema' if invalid == 'schema' else 'candle_time'] = -1
            return candidate
        q = BackgroundTraining(e, train)
        submit(q)
        task = asyncio.create_task(q.run())
        await until(lambda: q.discarded == 1)
        assert not e.controllers
        await stop(task, e)
    asyncio.run(scenario())
