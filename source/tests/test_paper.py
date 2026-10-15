import asyncio
import math
import time

import pytest

from engine.core import Engine
from engine.margin import margin_status
from engine.stream import normalize
from engine.learning import train_observer
from engine.research import demo_candles
from engine.models import Signal


def test_default_is_empty_real_data_account(tmp_path):
    e=Engine(tmp_path)
    assert e.mode=='PAPER'
    assert not e.state['closed'] and not e.state['markets']
    assert e.equity()==10000
    assert not e.state['running']


def test_start_balance_archives_previous_session(tmp_path):
    e=Engine(tmp_path)
    old_id=e.state['session_id']
    assert asyncio.run(e.command('paper_session',{'balance':12500}))['ok']
    assert e.equity()==12500 and e.state['running'] and e.mode=='PAPER'
    assert all(v==3125 for v in e.state['wallets'].values())
    assert e.store.get('archive:paper:'+old_id)['initial']==10000
    session=e.state['session_id']
    assert not asyncio.run(e.command('paper_session',{'balance':float('nan')}))['ok']
    assert e.state['session_id']==session


@pytest.mark.parametrize('side',['long','short'])
def test_margin_equation_includes_funding_and_exit_cost(side):
    p=dict(market='futures',entry=100,quantity=2,leverage=3,side=side,fee_rate=.0006,funding=-2)
    m=margin_status(p,100)
    threshold=margin_status(p,m['liquidation_price'])
    assert threshold['margin_equity']==pytest.approx(threshold['maintenance_margin'])
    assert m['liquidation_buffer']>0
    unfunded=margin_status({**p,'funding':0},100)
    assert abs(m['liquidation_price']-100)<abs(unfunded['liquidation_price']-100)


def test_liquidation_precedes_stop_and_isolates_loss(tmp_path):
    e=Engine(tmp_path)
    e.mode='DEMO'
    e.state['running']=True
    q=e.quote('Binance','BTCUSDT','futures')
    sig=Signal(strategy='intraday',symbol='BTCUSDT',venue='Binance',market='futures',side='long',
               price=q['price'],stop=q['price']*.98,target=q['price']*1.04,reason='test',candle_time=int(time.time()))
    assert e.open_signal(sig)['ok']
    p=e.state['positions'][0]
    before=e.state['wallets']['Binance:futures']
    collateral=p['initial_margin']
    q.update(price=p['entry']*.1,mark_price=p['entry']*.1,bid=p['entry']*.0999,
             ask=p['entry']*.1001,observed=time.time(),mark_price_observed=time.time())
    e.check_positions()
    closed=e.state['closed'][-1]
    assert closed['liquidated'] and closed['reason']=='Tahmini tasfiye'
    assert e.state['wallets']['Binance:futures']==pytest.approx(before-collateral)
    assert closed['net']==pytest.approx(-collateral-p['entry_fee'])
    assert closed['settlement_adjustment']>0


def test_bybit_delta_and_spot_orderbook_normalization():
    ticker=normalize('Bybit','futures',dict(topic='tickers.BTCUSDT',ts=int(time.time()*1000),
        data=dict(symbol='BTCUSDT',markPrice='75001.2',fundingRate='-0.0001')))
    assert ticker['mark_price']==75001.2 and 'bid' not in ticker and 'observed' not in ticker
    book=normalize('Bybit','spot',dict(topic='orderbook.1.BTCUSDT',data=dict(s='BTCUSDT',b=[['75000','2']],a=[['75001','3']])))
    assert book['bid']==75000 and book['ask_size']==3 and 'price' not in book
    assert normalize('Binance','futures',dict(e='markPriceUpdate',s='BTCUSDT',p='nan')) is None
    assert normalize('Binance','futures',dict(e='markPriceUpdate',s='BTCUSDT',p='5',E=1)) is None


def test_partial_stream_is_not_an_executable_quote(tmp_path):
    e=Engine(tmp_path)
    asyncio.run(e.stream_update(dict(venue='Bybit',market='spot',symbol='BTCUSDT',price=75000,observed=time.time())))
    assert not e.snapshot()['markets']
    e.check_positions()  # No missing bid/ask exception.


def test_funding_stays_in_isolated_margin_not_free_wallet(tmp_path):
    e=Engine(tmp_path)
    e.state['wallets']['Binance:futures']=1000
    e.state['positions']=[dict(venue='Binance',market='futures',quantity=1,entry=100,leverage=2,initial_margin=50,funding=-5)]
    e.state['wallets']['Binance:futures']-=5
    assert e.available('Binance','futures')==950


def test_current_trade_price_cannot_fill_against_stale_book(tmp_path):
    e=Engine(tmp_path)
    e.state['markets']=[dict(venue='Binance',symbol='BTCUSDT',market='futures',price=100,bid=99,ask=101,
                           observed=time.time(),bid_observed=time.time()-20,ask_observed=time.time()-20)]
    e.state['positions']=[dict(id='stale',venue='Binance',symbol='BTCUSDT',market='futures')]
    result=e.close_position('stale')
    assert not result['ok']
    assert len(e.state['positions'])==1


def test_learning_has_embargo_and_never_uses_unresolved_labels():
    rows=demo_candles(count=1800)
    model=train_observer(rows,'intraday','futures')
    assert model['status']=='observing'
    assert model['training_end']<model['evaluation_start']
    assert model['evaluation_samples']>50
    assert 0<=model['score']<=1
    assert len(model['coefficients'])==5
    assert math.isfinite(model['brier'])
    # Editing only the last unresolved close may alter the score, never fitted weights.
    changed=[dict(r) for r in rows]
    changed[-1]['close']*=1.01
    again=train_observer(changed,'intraday','futures')
    assert model['version']==again['version']
