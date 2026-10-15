"""Financial invariants reproduced during the 0.7.1 source audit."""
import copy
import time

import pytest

from engine.models import Signal
from test_exits import opened, set_execution


@pytest.mark.parametrize('side', ['long', 'short'])
@pytest.mark.parametrize('rate', [.01, -.01])
@pytest.mark.parametrize('partial', [False, True])
def test_late_funding_cannot_change_isolated_liquidation_loss(tmp_path, side, rate, partial):
    results=[]
    for arrival in ('before', 'after'):
        e,p=opened(tmp_path/arrival,side=side)
        sign=1 if side=='long' else -1
        p['opened_at']=time.time()-100
        event=dict(time=time.time()-50,rate=rate,mark=100)
        q=e.quote('Binance','BTCUSDT','futures')
        q['settlements']=[event]
        if arrival=='before':e.apply_funding(q)
        if partial:
            set_execution(e,p,p['entry']+sign*2.2)
            assert e.partial_position(p['id'])['ok']
        set_execution(e,p,p['entry']+sign*3,mark=p['entry']*(.1 if sign==1 else 2))
        e.check_positions()
        if arrival=='after':e.apply_funding(q)
        c=e.state['closed'][0]
        assert c['liquidated']
        assert e.equity()-e.state['initial']==pytest.approx(c['net'])
        assert c['net']==pytest.approx(c['gross']-c['fees']+c['funding']+c['settlement_adjustment'])
        before=copy.deepcopy(e.state)
        e.apply_funding(q)
        assert e.state==before
        assert e.store.get('adaptive_feedback')[0]['net']==pytest.approx(c['net'])
        results.append(c['net'])
    assert results[0]==pytest.approx(results[1])


def test_legacy_liquidated_close_can_reconcile_late_funding(tmp_path):
    e,p=opened(tmp_path)
    p['opened_at']=time.time()-100
    q=set_execution(e,p,p['entry']+3,mark=p['entry']*.1)
    e.check_positions()
    c=e.state['closed'][0]
    c.pop('final_fill')
    before=e.equity()
    q['settlements']=[dict(time=time.time()-50,rate=.01,mark=100)]
    e.apply_funding(q)
    assert e.equity()==pytest.approx(before)
    assert c['net']==pytest.approx(-c['initial_margin']-c['entry_fee'])


@pytest.mark.parametrize('multiplier,news,factor', [(1,'observe',1),(.25,'observe',.25),(1,'reduce',.5),(.25,'reduce',.125)])
def test_small_task_risk_cap_keeps_learning_and_news_reductions(tmp_path,monkeypatch,multiplier,news,factor):
    e,p=opened(tmp_path)
    assert e.close_position(p['id'])['ok']
    e.settings.risk_profile='custom'
    e.settings.local_ai_enabled=True
    e.settings.local_ai_news_controls=True
    monkeypatch.setattr('engine.core.active_news_risk',lambda *args:(news,'test'))
    sig=Signal(strategy='intraday',symbol='BTCUSDT',venue='Binance',market='futures',side='long',
        price=100,stop=99.9,target=100.2,reason='test',candle_time=int(time.time()//900)*900-900,
        risk_multiplier=multiplier,model_score=.8)
    result=e.open_signal(sig,absolute_risk_cap=.5,budget_limit=100,requested_leverage=2,preview=True)
    assert result['ok'],result
    assert result['planned_risk']<=.5*factor
    assert result['planned_risk']==pytest.approx(.5*factor,abs=.00003)


@pytest.mark.parametrize('side,current,distance', [('long',1,99),('short',20,60)])
def test_price_gap_cannot_create_nonpositive_protection(tmp_path,side,current,distance):
    e,p=opened(tmp_path,side=side)
    assert e.close_position(p['id'])['ok']
    q=e.quote('Binance','BTCUSDT','futures')
    q.update(price=current,bid=current*.9999,ask=current*1.0001,mark_price=current)
    sign=1 if side=='long' else -1
    sig=Signal(strategy='intraday',symbol='BTCUSDT',venue='Binance',market='futures',side=side,
        price=100,stop=100-sign*distance,target=100+sign*(distance if side=='short' else 2*distance),
        reason='gap',candle_time=int(time.time()//900)*900-900)
    outcome=e.open_signal(sig)
    assert not outcome['ok'] and 'stop/hedef' in outcome['message']
    assert not e.state['positions']


@pytest.mark.parametrize('kind', ['crossed','infinite','open_candle'])
def test_invalid_quote_and_unclosed_candle_cannot_enter(tmp_path,kind):
    e,p=opened(tmp_path)
    assert e.close_position(p['id'])['ok']
    q=e.quote('Binance','BTCUSDT','futures')
    candle=int(time.time()//900)*900-900
    if kind=='crossed':q.update(bid=101,ask=100)
    elif kind=='infinite':q.update(price=float('inf'),bid=float('inf'),ask=float('inf'))
    else:candle=int(time.time()//900)*900
    sig=Signal(strategy='intraday',symbol='BTCUSDT',venue='Binance',market='futures',side='long',
        price=100,stop=98,target=104,reason='invalid',candle_time=candle)
    outcome=e.open_signal(sig)
    assert not outcome['ok'] and not e.state['positions']


def test_crossed_or_infinite_book_cannot_close_or_revalue_position(tmp_path):
    e,p=opened(tmp_path)
    q=e.quote('Binance','BTCUSDT','futures')
    original=p['price']
    for bid,ask in [(110,100),(float('inf'),float('inf'))]:
        q.update(bid=bid,ask=ask)
        assert not e.close_position(p['id'])['ok']
        e.check_positions()
        assert e.state['positions'] and p['price']==original


@pytest.mark.parametrize('side,mark_factor', [('short',30),('long',.001)])
def test_isolated_mark_loss_cannot_spend_other_wallets_while_book_is_stale(tmp_path,side,mark_factor):
    e,p=opened(tmp_path,side=side)
    q=e.quote('Binance','BTCUSDT','futures')
    equity_at_entry=e.equity()
    q.update(mark_price=p['entry']*mark_factor,mark_price_observed=time.time(),
             bid_observed=time.time()-20,ask_observed=time.time()-20)
    e.check_positions()
    assert e.state['positions'] # Fresh mark must not fabricate an executable close.
    assert e.equity()==pytest.approx(equity_at_entry-(100-p['entry'])*(1 if side=='long' else -1)*p['quantity']-p['initial_margin'])
    assert e.equity()>0
    assert e.snapshot()['positions'][0]['unrealized']==pytest.approx(-p['initial_margin'])


@pytest.mark.parametrize('side,price_factor', [('short',30),('long',.001)])
def test_close_estimate_obeys_same_isolated_cash_limit_as_actual_close(tmp_path,side,price_factor):
    e,p=opened(tmp_path,side=side)
    set_execution(e,p,p['entry']*price_factor)
    estimate=e.snapshot()['positions'][0]['net_if_close']
    assert estimate==pytest.approx(-p['initial_margin']-p['entry_fee'])
    assert e.close_position(p['id'])['ok']
    assert e.state['closed'][0]['net']==pytest.approx(estimate)
    assert e.equity()-e.state['initial']==pytest.approx(estimate)
