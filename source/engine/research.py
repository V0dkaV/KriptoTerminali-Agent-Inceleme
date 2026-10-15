from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from engine.market import Exchange

INTERVALS = {'15m': 900, '1h': 3600, '4h': 14400, '1d': 86400}
EXECUTION_MODEL = 'bar-causal-v2'


def demo_candles(symbol='BTCUSDT', interval='15m', count=1600):
    step = INTERVALS[interval]
    end = int(time.time() // step) * step - step
    t = np.arange(count)
    rng = np.random.default_rng(73 if symbol == 'BTCUSDT' else 29)
    returns = rng.normal(0.000025, 0.0018 if symbol == 'BTCUSDT' else 0.0024, count)
    returns += np.sin(t / 77) * 0.00022
    closes = np.exp(np.cumsum(returns))
    closes *= (76984.6 if symbol == 'BTCUSDT' else 2894.72) / closes[-1]
    opens = np.r_[closes[0], closes[:-1]]
    spread = rng.uniform(0.0006, 0.0025, count)
    return [dict(time=int(end - (count - 1 - i) * step), open=float(opens[i]),
                 high=float(max(opens[i], closes[i]) * (1 + spread[i])),
                 low=float(min(opens[i], closes[i]) * (1 - spread[i])), close=float(closes[i]),
                 volume=float(rng.uniform(15, 290))) for i in range(count)]


def features(rows, strategy='intraday'):
    df = pd.DataFrame(rows).drop_duplicates('time').sort_values('time')
    df.index = pd.to_datetime(df.time, unit='s', utc=True)
    signal_step = 900 if strategy == 'intraday' else 14400
    high_rule = '1h' if strategy == 'intraday' else '1D'
    high_seconds = 3600 if strategy == 'intraday' else 86400
    higher = df.resample(high_rule).agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
    higher['fast'] = higher.close.ewm(span=50, adjust=False, min_periods=50).mean()
    higher['slow'] = higher.close.ewm(span=200, adjust=False, min_periods=200).mean()
    # A higher-timeframe candle becomes available only at its CLOSE time.
    higher.index = higher.index + pd.Timedelta(seconds=high_seconds)
    lookup = pd.DataFrame(index=df.index + pd.Timedelta(seconds=signal_step))
    trend = pd.merge_asof(lookup, higher[['fast', 'slow']], left_index=True, right_index=True, direction='backward')
    df['fast'], df['slow'] = trend.fast.to_numpy(), trend.slow.to_numpy()
    previous = df.close.shift(1)
    tr = pd.concat([df.high - df.low, (df.high - previous).abs(), (df.low - previous).abs()], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    window = 20 if strategy == 'intraday' else 55
    upper = df.high.rolling(window).max().shift(1)
    lower = df.low.rolling(window).min().shift(1)
    df['signal'] = np.select([(df.fast > df.slow) & (df.close > upper), (df.fast < df.slow) & (df.close < lower)], [1, -1], default=0)
    df['momentum'] = df.close.pct_change(12).fillna(0)
    df['volatility'] = df.close.pct_change().rolling(24).std().fillna(0)
    df['volume_ratio'] = (df.volume / df.volume.rolling(20).mean()).fillna(1)
    df['trend_strength'] = ((df.fast - df.slow) / df.close).fillna(0)
    return df


def recent_contiguous(rows, strategy, lookback=80):
    """Do not form current indicator signals across recent missing raw bars."""
    step = 900 if strategy == 'intraday' else 14400
    times = [int(row['time']) for row in rows[-lookback:]]
    return bool(times) and all(b - a == step for a, b in zip(times, times[1:]))


def analyze_candles(rows, strategy, market):
    df = features(rows, strategy)
    r = df.iloc[-1]
    contiguous = recent_contiguous(rows, strategy)
    ready=contiguous and math.isfinite(r.fast) and math.isfinite(r.slow) and math.isfinite(r.atr)
    ratio=float(r.atr/r.close) if ready else 0
    trend=float((r.fast-r.slow)/r.close) if ready else 0
    regime='unavailable' if not ready else 'volatile' if ratio>0.025 else 'uptrend' if trend>0.002 else 'downtrend' if trend<-.002 else 'range'
    context=dict(regime=regime,atr_ratio=ratio,trend_strength=trend,observed=time.time(),
                 data_quality='complete' if contiguous else 'gap',
                 note='Son gösterge mumlarında veri boşluğu var; yeni giriş bekletiliyor.' if not contiguous
                      else 'Açıklanabilir sanal rejim kuralı; tahmin olasılığı değildir.')
    side = int(r.signal)
    if not ready or not side or (side == -1 and market == 'spot'):
        return None,context
    distance = float(r.atr) * (2 if strategy == 'intraday' else 3)
    return dict(side='long' if side == 1 else 'short', price=float(r.close),
                stop=float(r.close) - side * distance, target=float(r.close) + side * 2 * distance,
                candle_time=int(r.time), reason=f"Kapanmış mum kanal kırılımı; {'1s' if strategy == 'intraday' else 'günlük'} EMA 50/200 teyidi."),context


def signal_at_close(rows,strategy,market):
    return analyze_candles(rows,strategy,market)[0]


def load_history(params, data_dir):
    strategy = params.get('strategy', 'intraday')
    interval = '15m' if strategy == 'intraday' else '4h'
    step = INTERVALS[interval]
    months = int(params.get('months', 36))
    warmup_days = 12 if strategy == 'intraday' else 220
    days = months * 30 + warmup_days
    count = int(days * 86400 / step)
    if params.get('source', 'DEMO') == 'DEMO':
        return demo_candles(params['symbol'], interval, count), [], 'DEMO', None
    venue, symbol, market = params['venue'], params['symbol'], params['market']
    cache = Path(data_dir) / 'history'
    cache.mkdir(parents=True, exist_ok=True)
    file = cache / f'{venue}-{symbol}-{market}-{interval}-{months}.parquet'
    exchange = Exchange(venue)
    end = int(time.time() // step) * step
    start = end - days * 86400
    rows = []
    if file.exists() and time.time() - file.stat().st_mtime < 3600:
        rows = pd.read_parquet(file).to_dict('records')
    elif venue == 'Binance':
        cursor = start
        for _ in range(200):
            batch = exchange.candles(symbol, interval, market, 1000, start=cursor, end=end)
            if not batch: break
            rows.extend(batch)
            next_cursor = batch[-1]['time'] + step
            if next_cursor <= cursor: break
            cursor = next_cursor
            if cursor >= end: break
            time.sleep(0.07)
    else:
        cursor = end
        for _ in range(200):
            batch = exchange.candles(symbol, interval, market, 1000, start=start, end=cursor)
            if not batch: break
            rows.extend(batch)
            next_cursor = batch[0]['time'] - 1
            if next_cursor >= cursor: break
            cursor = next_cursor
            if cursor <= start: break
            time.sleep(0.07)
    if len(rows) < 1000:
        raise ValueError('Yeterli tarihsel veri alınamadı; farklı borsa veya daha uzun dönem seçin.')
    rows = pd.DataFrame(rows).drop_duplicates('time').sort_values('time').to_dict('records')
    pd.DataFrame(rows).to_parquet(file, index=False)
    funding = []
    funding_error = None
    if market == 'futures':
        try:
            if venue == 'Binance':
                cursor = start * 1000
                for _ in range(30):
                    batch = exchange.public('/fapi/v1/fundingRate', dict(symbol=symbol, startTime=cursor, endTime=end*1000, limit=1000), market)
                    if not batch: break
                    funding.extend([(int(r['fundingTime']) // 1000, float(r['fundingRate'])) for r in batch])
                    cursor = int(batch[-1]['fundingTime']) + 1
                    if len(batch) < 1000: break
            else:
                cursor = end * 1000
                for _ in range(40):
                    batch = exchange.public('/v5/market/funding/history', dict(category='linear', symbol=symbol, startTime=start*1000, endTime=cursor, limit=200), market)['result']['list']
                    if not batch: break
                    funding.extend([(int(r['fundingRateTimestamp']) // 1000, float(r['fundingRate'])) for r in batch])
                    cursor = min(int(r['fundingRateTimestamp']) for r in batch) - 1
                    if len(batch) < 200: break
            if not funding: funding_error = 'Fonlama geçmişi eksik; rapor canlı onayı için kullanılamaz.'
        except Exception:
            funding_error = 'Fonlama geçmişi alınamadı; bu maliyet bilinmiyor.'
    return rows, sorted(set(funding)), 'PUBLIC', funding_error


def run_backtest(params, data_dir):
    strategy = params.get('strategy', 'intraday')
    rows, funding_rows, source, funding_error = load_history(params, data_dir)
    df = features(rows, strategy)
    step = 900 if strategy == 'intraday' else 14400
    warmup_cut = int(df.time.iloc[-1]) - int(params.get('months', 36)) * 30 * 86400
    holdout_cut = int(df.time.iloc[-1]) - 180 * 86400
    fee = float(params.get('fee_bps', 10 if params['market'] == 'spot' else 6)) / 10000
    slip = float(params.get('slippage_bps', 3)) / 10000
    equity, peak, max_dd = 10000.0, 10000.0, 0.0
    position = None
    trades, curve = [], []
    funding_map = {}
    for stamp, rate in funding_rows:
        bucket = stamp // step * step
        funding_map[bucket] = funding_map.get(bucket, 0.0) + rate
    values = df.to_dict('records')
    for i in range(1, len(values)):
        r, prev = values[i], values[i-1]
        if r['time'] < warmup_cut: continue
        # Decide at this candle's open, then evaluate its complete price range.
        # A position closed later inside the candle cannot retroactively finance
        # another entry at that same open.
        if position is None and i < len(values)-1 and prev['signal'] and (prev['signal'] == 1 or params['market'] == 'futures'):
            if math.isfinite(prev['atr']) and prev['atr'] > 0 and prev['time'] + step == r['time']:
                side = int(prev['signal'])
                entry = r['open'] * (1 + side * slip)
                dist = prev['atr'] * (2 if strategy == 'intraday' else 3)
                qty = min(equity * 0.005 / (dist + 2*fee*entry), equity * (1 if params['market'] == 'spot' else 3) / entry)
                position = dict(entry=entry, qty=qty, side=side, stop=entry-side*dist, target=entry+side*2*dist,
                                time=r['time'], index=i, funding=0,
                                features=[prev[k] for k in ('momentum', 'volatility', 'volume_ratio', 'trend_strength')])
        if position:
            p = position
            rate = funding_map.get(r['time'], 0)
            if source == 'DEMO' and params['market'] == 'futures' and r['time'] % 28800 == 0:
                rate = 0.0001  # Explicitly hypothetical demo funding.
            p['funding'] -= p['side'] * p['qty'] * r['open'] * rate
            exit_price, reason = None, ''
            if p['side'] == 1:
                if r['open'] <= p['stop']: exit_price, reason = r['open'], 'Stop / fiyat boşluğu'
                elif r['low'] <= p['stop']: exit_price, reason = p['stop'], 'Stop'
                elif r['high'] >= p['target']: exit_price, reason = p['target'], 'Hedef'
            else:
                if r['open'] >= p['stop']: exit_price, reason = r['open'], 'Stop / fiyat boşluğu'
                elif r['high'] >= p['stop']: exit_price, reason = p['stop'], 'Stop'
                elif r['low'] <= p['target']: exit_price, reason = p['target'], 'Hedef'
            if exit_price is None and (i - p['index'] + 1 >= (16 if strategy == 'intraday' else 42) or i == len(values)-1):
                exit_price, reason = r['close'], 'Süre / dönem sonu'
            if exit_price is not None:
                exit_price *= 1 - p['side'] * slip
                gross = (exit_price - p['entry']) * p['qty'] * p['side']
                fees = (p['entry'] + exit_price) * p['qty'] * fee
                net = gross - fees + p['funding']
                equity += net
                trades.append(dict(time=r['time'], entry_time=p['time'], side='long' if p['side'] == 1 else 'short',
                                   entry=p['entry'], exit=exit_price, quantity=p['qty'], gross=gross, fees=fees,
                                   funding=p['funding'], net=net, reason=reason,
                                   holdout=bool(p['time'] >= holdout_cut), features=p['features']))
                position = None
        marked = equity
        if position:
            marked += (r['close'] - position['entry']) * position['qty'] * position['side'] + position['funding']
            marked -= (position['entry'] + r['close']) * position['qty'] * fee
        peak = max(peak, marked)
        max_dd = max(max_dd, (peak-marked)/peak*100)
        if i % max(1, len(values)//400) == 0:
            curve.append(dict(time=r['time'], value=round(marked, 2)))
    def stats(items):
        wins = sum(t['net'] > 0 for t in items)
        gains = sum(max(t['net'], 0) for t in items)
        losses = -sum(min(t['net'], 0) for t in items)
        return dict(count=len(items), net=round(sum(t['net'] for t in items), 2), win_rate=round(wins/max(1, len(items))*100, 2),
                    profit_factor=round(gains/losses, 3) if losses else None,
                    fees=round(sum(t['fees'] for t in items), 2), funding=round(sum(t['funding'] for t in items), 2))
    gaps = sum(values[i]['time'] - values[i-1]['time'] > step for i in range(1, len(values)))
    holdout = stats([t for t in trades if t['holdout']])
    return dict(kind='backtest', execution_model=EXECUTION_MODEL, strategy=strategy, symbol=params['symbol'], market=params['market'], venue=params['venue'], source=source,
                months=params.get('months', 36), summary=stats(trades), holdout=holdout, max_drawdown=round(max_dd, 2),
                curve=curve, trades=trades[-1000:], training_trades=trades, gaps=gaps,
                warnings=[x for x in [funding_error, 'Komisyon hesabı varsayımsaldır; hesap oranıyla doğrulanmalıdır.',
                                      'DEMO: sentetik fiyatlar, gerçek performans değildir.' if source == 'DEMO' else None,
                                      'Veri boşlukları tespit edildi.' if gaps else None] if x],
                eligible=False, fee_bps=fee*10000, slippage_bps=slip*10000,
                created_at=time.time())


def train_filter(params, data_dir):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import balanced_accuracy_score
    result = run_backtest(params, data_dir)
    records = result.pop('training_trades')
    train = [t for t in records if not t['holdout']]
    test = [t for t in records if t['holdout']]
    if len(train) < 60 or len(test) < 20:
        raise ValueError('Model için en az 60 geliştirme ve 20 bağımsız test işlemi gerekiyor.')
    # Each trade closes before the next entry; a seven-day embargo also separates folds.
    boundary = min(t['entry_time'] for t in test)
    train = [t for t in train if t['time'] < boundary - 7*86400]
    split = int(len(train)*0.75)
    a, b = train[:split], train[split:]
    if len(set(t['net'] > 0 for t in a)) < 2 or not b:
        raise ValueError('Eğitim etiketleri veya doğrulama örnekleri yetersiz.')
    model = HistGradientBoostingClassifier(max_iter=80, max_depth=3, learning_rate=0.06, random_state=17)
    model.fit([t['features'] for t in a], [int(t['net'] > 0) for t in a])
    probabilities = model.predict_proba([t['features'] for t in b])[:, 1]
    choices = []
    for threshold in (0.45, 0.5, 0.55, 0.6, 0.65):
        selected = [t for t, p in zip(b, probabilities) if p >= threshold]
        if len(selected) >= 10:
            choices.append((sum(t['net'] for t in selected), threshold))
    threshold = max(choices)[1] if choices else 0.5
    predicted = model.predict_proba([t['features'] for t in test])[:, 1]
    selected = [t for t, p in zip(test, predicted) if p >= threshold]
    import joblib
    import hashlib
    models=Path(data_dir)/'models'
    models.mkdir(parents=True,exist_ok=True)
    model_path=models/f"{params['strategy']}-{params['symbol']}-{int(time.time())}.joblib"
    joblib.dump({'model':model,'threshold':threshold,'source':result['source'],'execution_model':result['execution_model'],
                 'feature_order':['momentum','volatility','volume_ratio','trend_strength']},model_path)
    model_hash=hashlib.sha256(model_path.read_bytes()).hexdigest()
    return dict(kind='ml', execution_model=result['execution_model'], source=result['source'], strategy=params['strategy'], symbol=params['symbol'],
                train_count=len(a), validation_count=len(b), test_count=len(test), selected_count=len(selected),
                baseline_net=round(sum(t['net'] for t in test), 2), filtered_net=round(sum(t['net'] for t in selected), 2),
                threshold=threshold, balanced_accuracy=round(float(balanced_accuracy_score([int(t['net'] > 0) for t in test], predicted >= threshold)), 3),
                eligible=False, status='research', created_at=time.time(),model_file=model_path.name,model_sha256=model_hash,
                warning='Araştırma karşılaştırmasıdır. Sonuçlar modelin canlı kullanımını onaylamaz; sessiz geri dönüş yoktur.')


def run_job(kind, params, data_dir):
    return train_filter(params, data_dir) if kind == 'ml' else run_backtest(params, data_dir)
