import asyncio
import time
import pytest
from engine.core import Engine
from engine.stream import normalize


@pytest.mark.parametrize('market',['spot','futures'])
def test_full_binance_ticker_keeps_last_price_and_book(market):
    stamp=int(time.time()*1000)
    r=normalize('Binance',market,dict(stream='btcusdt@ticker',data=dict(
        e='24hrTicker',E=stamp,s='BTCUSDT',c='80210.28',P='-3.27',q='100000000',
        b='80210.27',a='80210.29',B='2',A='3')))
    assert r['price']==80210.28 and r['volume']==100000000 and r['change']==-3.27
    assert r['bid']==80210.27 and r['ask']==80210.29
    assert r['price_observed']==pytest.approx(stamp/1000)
    assert r['price_transport']=='websocket'


def test_book_update_does_not_invent_or_refresh_last_trade(tmp_path):
    e=Engine(tmp_path)
    stamp=time.time()-8
    e.state['markets']=[dict(venue='Binance',market='spot',symbol='BTCUSDT',price=80208,
                           observed=stamp,price_observed=stamp,bid=80207.99,ask=80208.01,price_transport='rest')]
    book=normalize('Binance','spot',dict(u=123,s='BTCUSDT',b='80210.27',a='80210.29',B='2',A='3'))
    assert 'price' not in book and 'observed' not in book
    asyncio.run(e.stream_update(book))
    q=e.quote('Binance','BTCUSDT','spot')
    assert q['price']==80208 and q['price_observed']==stamp and q['price_transport']=='rest'
    ticker=normalize('Binance','spot',dict(e='24hrTicker',E=int(time.time()*1000),s='BTCUSDT',c='80210.28',
        b='80210.27',a='80210.29',B='2',A='3',q='100000000',P='-3.27'))
    asyncio.run(e.stream_update(ticker))
    q=e.quote('Binance','BTCUSDT','spot')
    assert q['price']==80210.28 and q['price_observed']>stamp and q['price_transport']=='websocket'
