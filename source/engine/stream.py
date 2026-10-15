"""Public price streams. No account keys and no order APIs."""
from __future__ import annotations

import asyncio
import json
import math
import time

from websockets.asyncio.client import connect


def normalize(venue, market, message):
    """Return a partial update; missing delta fields must never erase a quote."""
    r = message.get('data', message)
    if not isinstance(r, dict): return None
    symbol = r.get('s') if venue == 'Binance' else r.get('symbol') or r.get('s', '')
    if not symbol: return None
    stamp = float(message.get('ts') or r.get('E') or time.time()*1000)/1000
    if abs(time.time()-stamp)>30: return None
    out = dict(symbol=symbol, venue=venue, market=market, stream_observed=time.time())
    if venue == 'Binance':
        event = r.get('e', '')
        if event == 'markPriceUpdate':
            mapping = {'p':'mark_price','r':'funding'}
        else:
            # A 24hrTicker contains BOTH last trade (c) and best book (b/a).
            # These fields are not mutually exclusive. A raw bookTicker has no c.
            mapping = {'c':'price','q':'volume','P':'change',
                       'b':'bid','a':'ask','B':'bid_size','A':'ask_size'}
    elif message.get('topic', '').startswith('orderbook.'):
        mapping = {}
        for field, name in [('b','bid'),('a','ask')]:
            if r.get(field):
                out[name], out[name+'_size'] = map(float, r[field][0])
    else:
        mapping = {'lastPrice':'price','markPrice':'mark_price','fundingRate':'funding',
                   'bid1Price':'bid','ask1Price':'ask','bid1Size':'bid_size','ask1Size':'ask_size',
                   'price24hPcnt':'change','turnover24h':'volume'}
    for source, target in mapping.items():
        if r.get(source) not in (None, ''):
            value=float(r[source])
            if not math.isfinite(value): return None
            out[target]=value*(100 if venue=='Bybit' and target=='change' else 1)
    for field in ('price','bid','ask','mark_price'):
        if field in out:
            if out[field]<=0: return None
            out[field+'_observed']=stamp
    if 'price' in out:
        out['observed']=stamp
        out['price_transport']='websocket'
    return out if len(out)>5 else None


def subscription_batches(names):
    topics=[topic+s for s in names for topic in ('tickers.','orderbook.1.')]
    return [topics[i:i+10] for i in range(0,len(topics),10)]


async def listen(venue, market, channel, symbols, receive, stopping):
    delay=1
    while not stopping():
        try:
            names=list(symbols())
            if not names:
                await asyncio.sleep(1)
                continue
            if venue=='Binance':
                suffixes=['bookTicker'] if channel=='book' else ['ticker','markPrice@1s'] if market=='futures' else ['ticker','bookTicker']
                streams='/'.join(s.lower()+'@'+suffix for s in names for suffix in suffixes)
                base='wss://stream.binance.com:9443/stream' if market=='spot' else 'wss://fstream.binance.com/'+('public' if channel=='book' else 'market')+'/stream'
                url=base+'?streams='+streams
            else:
                url='wss://stream.bybit.com/v5/public/'+('linear' if market=='futures' else 'spot')
            async with connect(url,open_timeout=10,close_timeout=1,ping_interval=20,ping_timeout=20,max_size=1_000_000) as ws:
                if venue=='Bybit':
                    for batch in subscription_batches(names):
                        await ws.send(json.dumps(dict(op='subscribe',args=batch)))
                        await asyncio.sleep(.1)
                delay=1
                last_ping=time.monotonic()
                while not stopping() and names==list(symbols()):
                    try:
                        message=json.loads(await asyncio.wait_for(ws.recv(),timeout=10))
                        update=normalize(venue,market,message)
                        if update: await receive(update)
                    except asyncio.TimeoutError:
                        pass
                    if venue=='Bybit' and time.monotonic()-last_ping>18:
                        await ws.send('{"op":"ping"}')
                        last_ping=time.monotonic()
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(delay)
            delay=min(30,delay*2)
