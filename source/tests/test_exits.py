import copy
import time

import pytest

from engine.core import Engine
from engine.exits import adaptive_action, executable_price, quantity_at, remaining_net
from engine.models import Signal


def opened(tmp_path, market='futures', side='long', origin='strategy', policy='adaptive'):
    e=Engine(tmp_path)
    e.settings.exit_policy=policy
    now=time.time()
    e.state['running']=True
    e.news_sources=[dict(status='ok',observed=now)]
    e.state['markets']=[dict(venue='Binance',symbol='BTCUSDT',market=market,
        price=100.,bid=99.99,ask=100.01,observed=now,bid_observed=now,ask_observed=now,
        mark_price=100.,mark_price_observed=now,volume=10_000_000)]
    sign=1 if side=='long' else -1
    sig=Signal(strategy='intraday',symbol='BTCUSDT',venue='Binance',market=market,
        side=side,price=100,stop=100-sign*2,target=100+sign*4,reason='test',
        candle_time=int(now)//900*900-900,features=[.1]*19,model_version='test-model')
    assert e.open_signal(sig,origin=origin)['ok']
    p=e.state['positions'][0]
    return e,p


def set_execution(e,p,price,mark=None):
    q=e.quote(p['venue'],p['symbol'],p['market'])
    sign=1 if p['side']=='long' else -1
    raw=price/(1-sign*.0003)
    now=time.time()
    q.update(price=raw,bid=raw if sign==1 else raw-.02,
             ask=raw if sign==-1 else raw+.02,mark_price=mark or raw,
             observed=now,bid_observed=now,ask_observed=now,mark_price_observed=now)
    return q


@pytest.mark.parametrize('market,side',[('spot','long'),('futures','long'),('futures','short')])
def test_partial_then_final_reconciles_full_trade(tmp_path,market,side):
    e,p=opened(tmp_path,market,side)
    initial=e.state['initial']
    qty,risk,margin,fee=p['quantity'],p['planned_risk'],p['initial_margin'],p['entry_fee']
    sign=1 if side=='long' else -1
    set_execution(e,p,p['entry']+sign*2.2)
    e.check_positions()
    assert p['quantity']==pytest.approx(qty/2)
    assert p['planned_risk']==pytest.approx(risk/2)
    assert p['initial_margin']==pytest.approx(margin/2)
    assert p['entry_fee']==pytest.approx(fee/2)
    assert p['partial_realized']>0 and p['breakeven_active'] and p['trailing_active']
    assert not e.state['closed'] and not e.store.get('adaptive_feedback',[])
    assert len(p['partial_fills'])==1
    assert not e.partial_position(p['id'])['ok']
    # A trailing stop reversal can only execute at the available price.
    fill_price=p['stop']-sign*.1
    set_execution(e,p,fill_price)
    e.check_positions()
    assert not e.state['positions'] and len(e.state['closed'])==1
    c=e.state['closed'][0]
    assert c['quantity']==qty and c['planned_risk']==risk
    assert c['net']==pytest.approx(c['gross']-c['fees']+c['funding'])
    assert e.equity()-initial==pytest.approx(c['net'])
    assert c['final_exit']==pytest.approx(fill_price)
    feedback=e.store.get('adaptive_feedback',[])
    assert len(feedback)==1 and feedback[0]['r']==pytest.approx(c['net']/risk)
    assert not e.close_position(p['id'])['ok']


def test_trailing_never_loosens_and_full_target_precedes_partial(tmp_path):
    e,p=opened(tmp_path)
    set_execution(e,p,p['entry']+2.1)
    e.check_positions()
    stop=p['stop']
    set_execution(e,p,p['entry']+3.7)
    e.check_positions()
    assert p['stop']>stop
    stop=p['stop']
    set_execution(e,p,p['entry']+3.5)
    e.check_positions()
    assert p['stop']==stop
    e.close_position(p['id'])
    # New position jumps straight through full target: one full fill, no partial.
    e2,p2=opened(tmp_path/'other')
    set_execution(e2,p2,p2['target']+1)
    e2.check_positions()
    assert e2.state['closed'][0]['reason']=='Hedef'
    assert not e2.state['closed'][0]['partial_fills']


def test_executable_book_not_last_trade_controls_profit_and_stop(tmp_path):
    e,p=opened(tmp_path)
    q=e.quote('Binance','BTCUSDT','futures')
    q['price']=p['entry']+3
    e.check_positions()
    assert p['quantity']==p['original_quantity'] and not p['partial_fills']
    # Last trade is still profitable, but the sellable book gaps below stop.
    set_execution(e,p,p['stop']-1)
    q['price']=p['entry']+3
    e.check_positions()
    assert e.state['closed'][0]['reason']=='Stop'
    assert e.state['closed'][0]['final_exit']<p['initial_stop']


def test_liquidation_mark_precedes_profitable_book(tmp_path):
    e,p=opened(tmp_path)
    set_execution(e,p,p['entry']+3,mark=p['entry']*.1)
    e.check_positions()
    c=e.state['closed'][0]
    assert c['liquidated'] and not c['partial_fills']
    assert c['net']==pytest.approx(-p['original_initial_margin']-p['original_entry_fee'])


@pytest.mark.parametrize('side',['long','short'])
def test_late_funding_uses_historical_quantity_and_is_idempotent(tmp_path,side):
    e,p=opened(tmp_path,side=side)
    original=p['quantity']
    p['opened_at']=time.time()-100
    before_partial=time.time()-50
    sign=1 if side=='long' else -1
    q=set_execution(e,p,p['entry']+sign*2.2)
    e.check_positions()
    partial_at=p['partial_fills'][0]['closed_at']
    # Backdate only the receipt in this fixture so later funding is in the past.
    p['partial_fills'][0]['closed_at']=partial_at-10
    after_partial=partial_at-5
    q['settlements']=[dict(time=before_partial,rate=.001,mark=100),
                      dict(time=after_partial,rate=-.002,mark=100)]
    expected=-sign*original*100*.001+sign*(original/2)*100*.002
    before=e.equity()
    e.apply_funding(q)
    assert e.equity()-before==pytest.approx(expected)
    assert p['partial_fills'][0]['funding']==pytest.approx(-sign*original/2*100*.001)
    assert p['funding']==pytest.approx(-sign*original/2*100*.001+sign*original/2*100*.002)
    assert quantity_at(p,before_partial)==original
    assert quantity_at(p,after_partial)==original/2
    e.apply_funding(q)
    assert e.equity()-before==pytest.approx(expected)
    e.close_position(p['id'])
    c=e.state['closed'][0]
    assert c['funding']==pytest.approx(expected)
    assert e.equity()-e.state['initial']==pytest.approx(c['net'])
    # An old missing settlement arriving after final close updates one feedback row.
    q['settlements']=[dict(time=before_partial+1,rate=.001,mark=100)]
    e.apply_funding(q)
    expected-=sign*original*100*.001
    assert c['funding']==pytest.approx(expected)
    assert c['net']==pytest.approx(c['gross']-c['fees']+expected)
    assert e.equity()-e.state['initial']==pytest.approx(c['net'])
    assert len(e.store.get('adaptive_feedback'))==1
    assert e.store.get('adaptive_feedback')[0]['r']==pytest.approx(c['net']/p['initial_planned_risk'])


def test_funding_breakeven_includes_allocated_costs(tmp_path):
    e,p=opened(tmp_path)
    p['opened_at']=time.time()-10
    q=set_execution(e,p,p['entry']+2.2)
    q['settlements']=[dict(time=time.time()-1,rate=.001,mark=100)]
    e.apply_funding(q)
    e.check_positions()
    assert remaining_net(p,p['stop'])>=-1e-9
    assert p['stop']>p['entry']


def test_minimum_partial_falls_back_to_original_target(tmp_path):
    e,p=opened(tmp_path)
    # Explicit boundary unit case; retain normal wallet accounting elsewhere.
    p['quantity']=p['original_quantity']=.15
    price=p['entry']+2.2
    assert adaptive_action(p,price) is None
    assert not e.partial_position(p['id'])['ok']
    assert not p['partial_fills'] and p['target']==p['initial_target']


def test_restart_preserves_adaptive_state_and_legacy_remains_fixed(tmp_path):
    e,p=opened(tmp_path)
    set_execution(e,p,p['entry']+2.2)
    e.check_positions()
    restarted=Engine(tmp_path)
    saved=restarted.state['positions'][0]
    assert saved['quantity']==p['quantity'] and saved['stop']==p['stop']
    assert len(saved['partial_fills'])==1 and not restarted.state['running']
    # Absence of per-position policy is legacy fixed, regardless of new setting.
    saved.pop('exit_policy')
    assert adaptive_action(saved,saved['entry']+3) is None


def test_partial_atomic_rollback_and_manual_not_training(tmp_path,monkeypatch):
    e,p=opened(tmp_path,origin='chat')
    set_execution(e,p,p['entry']+2.2)
    before=copy.deepcopy(e.state)
    actual_save=e.save
    monkeypatch.setattr(e,'save',lambda: (_ for _ in ()).throw(OSError('disk unavailable')))
    with pytest.raises(OSError):e.partial_position(p['id'])
    assert e.state==before
    assert not e.store.db.execute("SELECT id FROM ledger WHERE kind='partial_trade'").fetchall()
    monkeypatch.setattr(e,'save',actual_save)
    assert e.partial_position(p['id'])['ok']
    assert e.close_position(p['id'])['ok']
    assert not e.store.get('adaptive_feedback',[])


def test_stale_book_cannot_partial_or_move_stop(tmp_path):
    e,p=opened(tmp_path)
    q=set_execution(e,p,p['entry']+2.2)
    q['bid_observed']=time.time()-20
    stop=p['stop']
    e.check_positions()
    assert p['stop']==stop and not p['partial_fills']


def test_fixed_new_entry_and_funding_restart_receipts(tmp_path):
    e,p=opened(tmp_path,policy='fixed')
    q=set_execution(e,p,p['entry']+2.2)
    e.check_positions()
    assert not p['partial_fills']
    q['settlements']=[dict(time=time.time(),rate=.001,mark=100)]
    e.apply_funding(q)
    saved_funding=p['funding']
    restarted=Engine(tmp_path)
    restarted.apply_funding(q)
    assert restarted.state['positions'][0]['funding']==saved_funding


def test_partial_frees_cash_margin_and_risk_without_second_commission(tmp_path):
    e,p=opened(tmp_path)
    q=set_execution(e,p,p['entry']+2.2)
    available=e.available('Binance','futures')
    fees=e.state['fees']
    initial_margin=p['initial_margin']
    original_entry_fee=p['entry_fee']
    assert e.partial_position(p['id'])['ok']
    f=p['partial_fills'][0]
    assert e.available('Binance','futures')-available==pytest.approx(initial_margin/2+f['gross']-f['exit_fee'])
    assert e.state['fees']-fees==pytest.approx(f['exit_fee'])
    assert p['entry_fee']+f['entry_fee']==original_entry_fee
    snap=e.snapshot()['positions'][0]
    assert snap['net_if_close']==pytest.approx(p['partial_realized']+remaining_net(p,executable_price(p,q)))
    assert snap['original_quantity']==2*snap['quantity']


def test_task_absolute_risk_cap_and_mission_id(tmp_path):
    e,p=opened(tmp_path)
    assert e.close_position(p['id'])['ok']
    q=e.quote('Binance','BTCUSDT','futures')
    sig=Signal(strategy='intraday',symbol='BTCUSDT',venue='Binance',market='futures',
        side='long',price=q['price'],stop=q['price']-2,target=q['price']+4,
        reason='task',candle_time=int(time.time())//900*900-900)
    result=e.open_signal(sig,absolute_risk_cap=1,mission_id='task-1')
    assert result['ok']
    assert e.state['positions'][0]['planned_risk']<=1
    assert e.state['positions'][0]['mission_id']=='task-1'
    for invalid in (0,-1,float('nan'),True):
        assert not e.open_signal(sig,absolute_risk_cap=invalid)['ok']
