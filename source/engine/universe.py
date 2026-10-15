"""Bounded exchange discovery and fair, rotating deep analysis.

Catalog discovery never sends orders or changes risk limits. Broad quotes are
distinct from a completed candle analysis and from a qualified entry signal.
"""
from __future__ import annotations

import math
import time

PRODUCTS = [(v, m) for v in ('Binance', 'Bybit') for m in ('spot', 'futures')]
MIN_VOLUME = 5_000_000
MAX_SPREAD = .5
MAX_SYMBOLS = 1500
REFRESH_SECONDS = 900


class Universe:
    def __init__(self, saved=None):
        saved = saved or {}
        self.catalogs = saved.get('catalogs', {})
        self.sources = saved.get('sources', {})
        self.last_refresh = 0.
        self.refresh_requested = True
        self.loading = False
        self.rotation = 0
        self.last_batch = []
        self.stream_cache = {}
        self.capacity_excluded = 0

    @staticmethod
    def key(venue, market):
        return venue + ':' + market

    def due(self):
        return not self.loading and (self.refresh_requested or time.time() - self.last_refresh >= REFRESH_SECONDS)

    def merge(self, results, now=None):
        now = now or time.time()
        for venue, market, rows, error in results:
            key = self.key(venue, market)
            old = self.sources.get(key, {})
            if error:
                self.sources[key] = dict(venue=venue, market=market, status='error',
                    count=len(self.catalogs.get(key, [])), error='Borsa listesi yenilenemedi; son başarılı liste korunuyor.',
                    updated_at=old.get('updated_at', 0), checked_at=now)
            else:
                self.catalogs[key] = sorted({r['symbol'] for r in rows})
                self.sources[key] = dict(venue=venue, market=market, status='ready',
                    count=len(self.catalogs[key]), error='', updated_at=now, checked_at=now)
        self.last_refresh = now
        self.refresh_requested = False
        self.stream_cache.clear()

    def saved(self):
        return dict(catalogs=self.catalogs, sources=self.sources)

    def discovered(self):
        return sorted({s for rows in self.catalogs.values() for s in rows})

    def aliases(self):
        # Only infer a multiplier when its underlying is independently listed.
        spot={s for v in ('Binance','Bybit') for s in self.catalogs.get(self.key(v,'spot'),[])}
        result={}
        for symbol in self.discovered():
            for prefix in ('10000000','1000000','100000','10000','1000','1M'):
                if symbol.startswith(prefix) and symbol[len(prefix):] in spot:
                    result[symbol]=symbol[len(prefix):]
                    break
        return result

    def canonical(self, symbol):
        return self.aliases().get(symbol,symbol)

    def supports(self, venue, symbol, market, fresh=False):
        key = self.key(venue, market)
        if fresh and time.time() - self.sources.get(key, {}).get('updated_at', 0) > 3600:
            return False
        return symbol in self.catalogs.get(key, [])

    @staticmethod
    def liquid(q, now=None):
        now = now or time.time()
        try:
            price, bid, ask, volume = (float(q.get(k, 0)) for k in ('price', 'bid', 'ask', 'volume'))
            return (all(math.isfinite(v) for v in (price, bid, ask, volume)) and price > 0 and 0 < bid <= ask
                and volume >= MIN_VOLUME and (ask - bid) / price * 100 <= MAX_SPREAD
                and all(now - q.get(k + '_observed', q.get('observed', 0)) <= 30 for k in ('price', 'bid', 'ask')))
        except (TypeError, ValueError):
            return False

    def ranked(self, engine):
        scores = {}
        allowed=set(engine.settings.allowlist)
        for q in engine.state['markets']:
            if q['symbol'] not in allowed or not self.liquid(q):
                continue
            if engine.settings.auto_universe and self.catalogs and not self.supports(q['venue'], q['symbol'], q['market'], fresh=True):
                continue
            scores[q['symbol']] = max(scores.get(q['symbol'], 0), q['volume'])
        return sorted(scores, key=lambda s: (-scores[s], s))

    def selection(self, engine):
        # Discovery broadens coins, never account/mode/mission permissions.
        pinned = sorted({p['symbol'] for state in engine.states.values() for p in state['positions']})
        names = self.discovered()
        ranks = {s: v for s, v in ((q['symbol'], q.get('volume', 0)) for q in engine.state['markets'])}
        names.sort(key=lambda s: (-ranks.get(s, 0), s))
        self.capacity_excluded = max(0, len(set(names) | set(pinned)) - MAX_SYMBOLS)
        return list(dict.fromkeys(pinned + names))[:MAX_SYMBOLS]

    def batch(self, engine):
        if not engine.settings.auto_universe or not self.catalogs:
            self.last_batch = list(engine.settings.allowlist)
            return self.last_batch
        names = self.ranked(engine)
        priority = names[:4]
        rest = sorted(set(names) - set(priority))
        take = min(12, len(rest))
        offset = self.rotation % max(1, len(rest))
        rotated = (rest[offset:] + rest[:offset])[:take]
        self.rotation = (offset + take) % max(1, len(rest))
        self.last_batch = priority + rotated
        return self.last_batch

    def streams(self, engine, venue, market):
        # Stable priorities avoid tearing down every stream on a deep-scan rotation.
        exposed = sorted({p['symbol'] for p in engine.state['positions'] if p['venue'] == venue and p['market'] == market})
        if not engine.settings.auto_universe or not self.catalogs:
            return list(dict.fromkeys(exposed + engine.settings.allowlist))[:72]
        listed = set(self.catalogs.get(self.key(venue, market), []))
        key=self.key(venue,market)
        if key not in self.stream_cache:
            volumes={q['symbol']:q['volume'] for q in engine.state['markets'] if q['venue']==venue and q['market']==market and q['symbol'] in listed and self.liquid(q)}
            if volumes:self.stream_cache[key]=sorted(volumes,key=lambda s:(-volumes[s],s))[:60]
        priority=self.stream_cache.get(key,[s for s in ('BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT') if s in listed])
        allowed=set(engine.settings.allowlist)
        return list(dict.fromkeys(exposed + [s for s in priority if s in allowed]))[:60 + len(exposed)]

    def snapshot(self, engine):
        auto = engine.settings.auto_universe
        if engine.mode=='DEMO':
            symbols=[s for s in engine.settings.allowlist if s in ('BTCUSDT','ETHUSDT')]
            return dict(mode='demo',status='manual',discovered=0,symbols=len(symbols),eligible=len(symbols),
                analyzed=len(engine.state.get('decisions',{})),expected=len(symbols)*4*sum(bool(v) for v in engine.enabled.values()),
                scan_batch_size=len(symbols),scan_batch=symbols,stream_symbols=0,updated_at=0,error='',sources=[],
                exclusions={},min_volume=MIN_VOLUME,max_spread=MAX_SPREAD,note='Demo yalnız BTC/ETH örnek grafiklerini kullanır; gerçek borsa keşfi Sanal moddadır.')
        sources = [self.sources.get(self.key(v, m), dict(venue=v, market=m, status='loading', count=0, updated_at=0, error='')) for v, m in PRODUCTS]
        failures = sum(s['status'] == 'error' for s in sources)
        status = 'manual' if not auto else 'loading' if self.loading or not self.catalogs else 'error' if failures == 4 else 'partial' if failures else 'ready'
        allowed = set(engine.settings.allowlist)
        decisions = [d for d in engine.state.get('decisions', {}).values() if d['symbol'] in allowed and engine.enabled.get(d['strategy'])]
        expected = sum(len(set(rows) & allowed) for rows in self.catalogs.values()) * sum(bool(v) for v in engine.enabled.values()) if auto and self.catalogs else len(allowed) * 4 * sum(bool(v) for v in engine.enabled.values())
        return dict(mode='auto' if auto else 'manual', status=status, discovered=len(self.discovered()),
            symbols=len(allowed), eligible=len(self.ranked(engine)), analyzed=len(decisions), expected=expected,
            scan_batch_size=16 if auto else len(allowed), scan_batch=self.last_batch,
            stream_symbols=len({s for v, m in PRODUCTS for s in self.streams(engine, v, m)}),
            updated_at=max([s.get('updated_at', 0) for s in sources], default=0),
            error='Bazı liste kaynaklarına erişilemiyor; önbellek ve kaynak zamanlarını kontrol edin.' if failures else '', sources=sources,
            exclusions=dict(capacity=self.capacity_excluded), min_volume=MIN_VOLUME, max_spread=MAX_SPREAD,
            note='Aktif USDT spot ve sürekli vadeli pariteler keşfedilir. Geniş fiyat taraması ayrıdır; likit coinlerin kapanmış mumları dönüşümlü incelenir. İlk hazırlık zaman alır; işlem ve kâr garantisi değildir.')
