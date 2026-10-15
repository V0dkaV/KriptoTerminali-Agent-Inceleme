"""A bounded model-training queue, independent of live market scans.

Only the newest closed candle per context is queued. Training never holds the
engine lock, and lifecycle changes invalidate both queued and completed work.
"""
from __future__ import annotations

import asyncio
import copy
import time
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from multiprocessing import get_context

from engine.adaptive import SCHEMA, update_controller


def reset_broken_pool(engine, pool):
    """Detach only the failed pool, never a newer replacement shared by AI work."""
    if pool is not None and engine.learning_pool is pool:
        engine.learning_pool = None
    if pool is not None:
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass


@dataclass(frozen=True)
class TrainingJob:
    mode: str
    session_id: str
    key: str
    rows: tuple
    strategy: str
    market: str
    candle_time: int


class BackgroundTraining:
    def __init__(self, engine, trainer, *, capacity=480, retry_seconds=30):
        self.engine = engine
        self.trainer = trainer
        self.capacity = max(1, int(capacity))
        self.retry_seconds = max(0, float(retry_seconds))
        self.pending = OrderedDict()
        self.wake = asyncio.Event()
        self.current = None
        self.failures = OrderedDict()
        self.last_duration = 0.0
        self.last_finished = 0.0
        self.completed = 0
        self.discarded = 0
        self.failed = 0
        self.last_error = ''

    def active(self, job):
        e = self.engine
        try:
            venue, symbol, market, strategy = job.key.split(':')
            return bool(not e.closing and job.mode == 'PAPER' and e.mode == job.mode
                        and e.state.get('session_id') == job.session_id
                        and e.state.get('running') and e.enabled.get(strategy)
                        and strategy == job.strategy and market == job.market
                        and symbol in e.settings.allowlist)
        except (ValueError, AttributeError):
            return False

    def stale(self, job):
        e = self.engine
        venue, symbol, market, strategy = job.key.split(':')
        cached = e.analysis_cache.get((job.mode, venue, symbol, market, strategy))
        if cached and cached[0] > job.candle_time:
            return True
        controller = e.controllers.get(job.key, {})
        latest = controller.get('latest', {})
        return bool(controller.get('schema') == SCHEMA
                    and latest.get('schema', SCHEMA) == SCHEMA
                    and latest.get('candle_time', -1) >= job.candle_time)

    def submit(self, mode, session_id, key, rows, strategy, market):
        if not rows:
            return False
        job = TrainingJob(mode, session_id, key, tuple(rows), strategy, market, int(rows[-1]['time']))
        if not self.active(job) or self.stale(job):
            return False
        identity = (mode, session_id, key)
        failure = self.failures.get(identity)
        if failure and failure > time.monotonic():
            return False
        if self.current and (self.current.mode, self.current.session_id, self.current.key) == identity:
            if self.current.candle_time >= job.candle_time:
                return False
        # Remove invalid old-session contexts before enforcing the memory bound.
        for old_identity, queued in list(self.pending.items()):
            if not self.active(queued):
                del self.pending[old_identity]
                self.discarded += 1
        previous = self.pending.get(identity)
        if previous and previous.candle_time >= job.candle_time:
            return False
        if previous is None and len(self.pending) >= self.capacity:
            self.discarded += 1
            return False
        self.pending[identity] = job
        self.wake.set()
        return True

    def snapshot(self):
        return dict(queued=len(self.pending), running=self.current is not None,
                    current_key=self.current.key if self.current else None,
                    completed=self.completed, discarded=self.discarded, failed=self.failed,
                    last_duration=round(self.last_duration, 3), last_finished=self.last_finished,
                    last_error=self.last_error)

    async def run(self):
        e = self.engine
        while not e.closing:
            if not self.pending:
                self.wake.clear()
                await self.wake.wait()
                continue
            identity, job = self.pending.popitem(last=False)
            if not self.active(job) or self.stale(job):
                self.discarded += 1
                continue
            self.current = job
            started = time.monotonic()
            pool = None
            try:
                # Feedback is captured when work actually starts, not when queued.
                actual = copy.deepcopy(e.feedback(job.key))
                if e.learning_pool is None:
                    e.learning_pool = ProcessPoolExecutor(max_workers=1, mp_context=get_context('spawn'))
                pool = e.learning_pool
                candidate = await asyncio.get_running_loop().run_in_executor(
                    pool, self.trainer, job.rows, job.strategy, job.market, actual)
                committed = False
                async with e.lock:
                    if (self.active(job) and not self.stale(job)
                            and candidate.get('schema') == SCHEMA
                            and candidate.get('candle_time') == job.candle_time):
                        e.controllers[job.key] = update_controller(copy.deepcopy(e.controllers.get(job.key, {})), candidate)
                        e.controllers_dirty = True
                        self.completed += 1
                        self.failures.pop(identity, None)
                        committed = True
                    else:
                        self.discarded += 1
                if committed:
                    # Re-evaluation uses current quotes/feedback; it can acquire the
                    # lock itself and cannot block other contexts' market scans.
                    callback = getattr(e, 'training_completed', None)
                    if callback:
                        await callback(job)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if isinstance(exc, BrokenProcessPool):
                    reset_broken_pool(e, pool)
                self.failed += 1
                self.last_error = type(exc).__name__
                self.failures[identity] = time.monotonic() + self.retry_seconds
                self.failures.move_to_end(identity)
                while len(self.failures) > self.capacity:
                    self.failures.popitem(last=False)
                try:
                    async with e.lock:
                        if self.active(job):
                            e.audit('model', 'Arka plan model eğitimi tamamlanamadı; yeniden denenecek.',
                                    dict(key=job.key, error=type(exc).__name__))
                except Exception:
                    pass
            finally:
                self.last_duration = time.monotonic() - started
                self.last_finished = time.time()
                self.current = None
