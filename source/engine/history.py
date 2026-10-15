"""Bounded, closed-bar public history. This service has no trading authority."""
from __future__ import annotations

import calendar
import hashlib
import json
import math
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from engine.market import Exchange

INTERVALS = {'4h': 14400, '1d': 86400}
COLUMNS = ['time', 'open', 'high', 'low', 'close', 'volume']


def calendar_start(now: float, months: int) -> int:
    current = datetime.fromtimestamp(now, timezone.utc)
    index = current.year * 12 + current.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    return int(current.replace(year=year, month=month,
                              day=min(current.day, calendar.monthrange(year, month)[1])).timestamp())


def _clean(rows, step, end):
    valid = {}
    for raw in rows:
        try:
            row = {k: int(raw[k]) if k == 'time' else float(raw[k]) for k in COLUMNS}
            if row['time'] % step or row['time'] + step > end:
                continue
            if not all(math.isfinite(row[k]) for k in COLUMNS):
                continue
            if min(row[k] for k in ('open', 'high', 'low', 'close')) <= 0 or row['volume'] < 0:
                continue
            if not row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high']:
                continue
            valid[row['time']] = row
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return sorted(valid.values(), key=lambda r: r['time'])


def _missing(rows, start, end, step):
    present = {r['time'] for r in rows}
    result = []
    for stamp in range(start, end, step):
        if stamp in present:
            continue
        if result and result[-1]['end'] + step == stamp:
            result[-1]['end'] = stamp
            result[-1]['missing'] += 1
        else:
            result.append(dict(start=stamp, end=stamp, missing=1))
    return result


def _ema_context(rows, step):
    observations = len(rows)
    contiguous = observations >= 200 and all(b['time'] - a['time'] == step for a, b in zip(rows[-200:], rows[-199:]))
    result = dict(trend='insufficient', ema50=None, ema200=None,
                  as_of=rows[-1]['time'] + step if rows else None, observations=observations, required=200)
    if not contiguous:
        return result
    close = pd.Series([r['close'] for r in rows], dtype=float)
    a, b = float(close.ewm(span=50, adjust=False).mean().iloc[-1]), float(close.ewm(span=200, adjust=False).mean().iloc[-1])
    last = rows[-1]['close']
    result.update(ema50=a, ema200=b,
                  trend='up' if last > a > b else 'down' if last < a < b else 'mixed')
    return result


def summarize(rows, full_rows, daily_rows, step, coverage):
    context = _ema_context(full_rows, step)
    daily = _ema_context(daily_rows, 86400)
    result = dict(return_pct=None, max_drawdown_pct=None, high=None, low=None,
                  annualized_volatility_pct=None, volume_total=None, volume_recent_vs_previous=None,
                  trend=context['trend'], ema50=context['ema50'], ema200=context['ema200'],
                  daily_context=daily, warmup_sufficient=coverage['warmup_actual'] >= 200,
                  as_of=context['as_of'], limitations=[])
    if coverage['status'] != 'complete':
        result['limitations'].append('İstenen aralığın verisi eksik; ölçümler yalnız eldeki mumlara dayanır.')
    if not result['warmup_sufficient']:
        result['limitations'].append('Görünür aralıktan önce 200 mum hazırlık verisi tamamlanmadı.')
    if daily['trend'] == 'insufficient':
        result['limitations'].append('Günlük EMA 50/200 için kesintisiz 200 kapanmış günlük mum yok.')
    if not rows:
        return result
    closes = np.asarray([rows[0]['open']] + [r['close'] for r in rows], dtype=float)
    peak = np.maximum.accumulate(closes)
    result.update(return_pct=(rows[-1]['close'] / rows[0]['open'] - 1) * 100,
                  max_drawdown_pct=float(np.max((peak - closes) / peak)) * 100,
                  high=max(r['high'] for r in rows), low=min(r['low'] for r in rows),
                  volume_total=sum(r['volume'] for r in rows))
    returns = [math.log(b['close'] / a['close']) for a, b in zip(rows, rows[1:]) if b['time'] - a['time'] == step]
    if len(returns) >= 2:
        result['annualized_volatility_pct'] = float(np.std(returns, ddof=1) * math.sqrt(365 * 86400 / step) * 100)
    window = max(1, 7 * 86400 // step)
    if len(rows) >= window * 2:
        recent, previous = rows[-window:], rows[-window * 2:-window]
        if all(b['time'] - a['time'] == step for a, b in zip(rows[-window * 2:], rows[-window * 2 + 1:])):
            previous_volume = sum(r['volume'] for r in previous)
            if previous_volume > 0:
                result['volume_recent_vs_previous'] = sum(r['volume'] for r in recent) / previous_volume
    result['limitations'].append('Hesap düşüşü kapanışlardan, oynaklık ardışık kapanış getirilerinden hesaplanır; işlem performansı değildir.')
    return result


class HistoryService:
    def __init__(self, directory, exchange_factory=Exchange, clock=time.time):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.exchange_factory, self.clock = exchange_factory, clock
        self._locks, self._guard, self._summaries = {}, threading.Lock(), {}

    def _lock(self, key):
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    def latest_summaries(self):
        """Already requested real-data summaries only; never initiates a download."""
        with self._guard:
            return json.loads(json.dumps(list(self._summaries.values())))

    def _series(self, symbol, venue, market, interval, start, end, deadline):
        step = INTERVALS[interval]
        key = f'{venue}-{market}-{symbol}-{interval}'
        path, meta_path = self.directory / (key + '.parquet'), self.directory / (key + '.json')
        with self._lock(key):
            try:
                rows = _clean(pd.read_parquet(path).to_dict('records'), step, end)
            except (OSError, ValueError, TypeError, KeyError):
                rows = []
            try:
                meta = json.loads(meta_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            missing = _missing(rows, start, end, step)
            # Unavailable listings and holes are retried after five minutes, not on every render.
            fingerprint = hashlib.sha256(json.dumps(missing, sort_keys=True).encode()).hexdigest()
            refresh = bool(missing) and (meta.get('fingerprint') != fingerprint or self.clock() - meta.get('attempted', 0) >= 300)
            error = False
            if refresh:
                exchange = self.exchange_factory(venue)
                budget = 12
                for gap in missing:
                    cursor = gap['start']
                    while cursor <= gap['end'] and budget > 0:
                        if time.monotonic() >= deadline:
                            error = True
                            break
                        budget -= 1
                        # Bound each requested window to 1,000 slots. Binance returns
                        # oldest-first while Bybit returns newest-first; either must
                        # cover the entire same window before advancing it.
                        window_end = min(gap['end'] + step, cursor + 1000 * step)
                        try:
                            page = exchange.candles(symbol, interval, market, limit=1000,
                                                    start=cursor, end=window_end - 1)
                            page = [r for r in _clean(page, step, end) if cursor <= r['time'] < window_end]
                        except Exception:
                            error = True
                            break
                        rows = _clean(rows + page, step, end)
                        cursor = window_end
                    if error or budget <= 0:
                        break
                # Retain at most two years plus EMA warmup. Every output is still separately bounded.
                rows = [r for r in rows if r['time'] >= end - 2 * 366 * 86400 - 200 * step]
                try:
                    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
                    pd.DataFrame(rows, columns=COLUMNS).to_parquet(temporary, index=False)
                    os.replace(temporary, path)
                    new_missing = _missing(rows, start, end, step)
                    metadata = dict(attempted=self.clock(), fingerprint=hashlib.sha256(json.dumps(new_missing, sort_keys=True).encode()).hexdigest(), error=error)
                    temporary_meta = meta_path.with_name(meta_path.name + '.' + uuid.uuid4().hex + '.tmp')
                    temporary_meta.write_text(json.dumps(metadata), encoding='utf-8')
                    os.replace(temporary_meta, meta_path)
                except (OSError, ValueError):
                    error = True
            else:
                error = bool(meta.get('error')) and bool(missing)
            return [r for r in rows if start <= r['time'] < end], error

    def get(self, symbol='BTCUSDT', venue='Binance', market='spot', months=6, interval='1d', source='PAPER'):
        if not re.fullmatch(r'[A-Z0-9]{1,16}USDT', symbol) or venue not in ('Binance', 'Bybit') or market not in ('spot', 'futures') or months not in (6, 12) or interval not in INTERVALS or source not in ('PAPER', 'DEMO'):
            raise ValueError('Geçersiz uzun dönem piyasa veya aralık.')
        now, step = self.clock(), INTERVALS[interval]
        deadline = time.monotonic() + 60
        requested_start = calendar_start(now, months)
        start, end = math.ceil(requested_start / step) * step, int(now // step) * step
        daily_start = (math.ceil(requested_start / 86400) - 200) * 86400
        daily_end = int(now // 86400) * 86400
        if source == 'DEMO':
            def demo(first, last, stride):
                result = []
                for stamp in range(first, last, stride):
                    base = 100 + 8 * math.sin(stamp / 86400 / 17) + (stamp % (366 * 86400)) / (366 * 86400) * 15
                    result.append(dict(time=stamp, open=base, high=base * 1.01, low=base * .99, close=base * (1 + .002 * math.sin(stamp / 86400)), volume=1000.0))
                return result
            full_rows, failed = demo(start - 200 * step, end, step), False
            daily_rows = full_rows if interval == '1d' else demo(daily_start, daily_end, 86400)
        else:
            full_rows, failed = self._series(symbol, venue, market, interval, start - 200 * step, end, deadline)
            if interval == '1d':
                daily_rows = full_rows
            else:
                daily_rows, daily_failed = self._series(symbol, venue, market, '1d', daily_start, daily_end, deadline)
                failed |= daily_failed
        visible = [r for r in full_rows if start <= r['time'] < end]
        gaps = _missing(visible, start, end, step)
        warmup = [r for r in full_rows if r['time'] < start]
        coverage = dict(status='complete' if not gaps else 'partial' if visible else 'unavailable',
                        actual=len(visible), expected=len(range(start, end, step)),
                        start=visible[0]['time'] if visible else None, end=visible[-1]['time'] if visible else None,
                        gaps=gaps, missing=sum(g['missing'] for g in gaps),
                        warmup_actual=len(warmup), warmup_required=200,
                        daily_actual=len(daily_rows), daily_expected=len(range(daily_start, daily_end, 86400)))
        summary = summarize(visible, full_rows, daily_rows, step, coverage)
        if source == 'DEMO':
            summary['limitations'].insert(0, 'Örnek üretilmiş DEMO verisidir; gerçek piyasa analizi değildir.')
        response = dict(rows=visible, source=source, summary=summary, coverage=coverage,
                        range=dict(months=months, interval=interval, requested_start=requested_start, requested_end=end),
                        stale=failed or coverage['status'] != 'complete')
        if failed:
            response['error'] = 'Geçmiş verinin bir bölümü alınamadı; varsa önbellekteki gerçek mumlar gösterilir.'
        elif coverage['status'] != 'complete':
            response['error'] = 'İstenen dönemin tüm mumları kaynakta bulunamadı; eksik yerler doldurulmadı.'
        if source == 'PAPER':
            with self._guard:
                key = (venue, symbol, market, months, interval)
                self._summaries.pop(key, None)
                self._summaries[key] = dict(symbol=symbol, venue=venue, market=market,
                    months=months, interval=interval, summary=summary, coverage=coverage, observed=now, source=source)
                while len(self._summaries) > 4:
                    self._summaries.pop(next(iter(self._summaries)))
        return response
