import asyncio
import json
import math
import time
import sqlite3
import pytest
import numpy as np
from pydantic import ValidationError
from engine.core import Engine
from engine.models import GroupMachine, RiskSettings, Signal, net_pnl, position_size
from engine.store import Store
from engine.news import entry_restriction
from engine.research import demo_candles, features, run_backtest


@pytest.fixture
def engine(tmp_path):
    value=Engine(tmp_path)
    value.mode='DEMO'
    value.state['running']=True
    return value


def make_signal(engine,symbol='BTCUSDT',venue='Binance',market='futures',side='long'):
    q=engine.quote(venue,symbol,market)
    sign=1 if side=='long' else -1
    return Signal(strategy='intraday',symbol=symbol,venue=venue,market=market,side=side,
        price=q['price'],stop=q['price']*(1-sign*.015),target=q['price']*(1+sign*.03),
        reason='test',candle_time=int(time.time()))


@pytest.mark.parametrize('gross,fee,funding,expected',[(20,2,-3,15),(20,2,3,21),(-10,2,0,-12),(0,.3,.1,-.2)])
def test_signed_funding_and_single_fee(gross,fee,funding,expected):
    assert net_pnl(gross,fee,funding)==pytest.approx(expected)


@pytest.mark.parametrize('leverage',[1,2,3])
def test_size_includes_cost_and_margin(leverage):
    qty,risk=position_size(10000,70000,69000,.5,.001,100,leverage)
    assert risk<=50
    assert qty*70000/leverage+qty*70000*.001<=100+1e-8


def test_invalid_limits_not_accepted():
    for values in ({'trade_risk':2},{'total_risk':5},{'leverage':6},{'max_positions':13},{'paper_balance':float('nan')}):
        with pytest.raises(ValidationError): RiskSettings(**values)


def test_atomic_ledger_rollback(tmp_path):
    store=Store(tmp_path)
    with pytest.raises(RuntimeError):
        with store.atomic():
            store.ledger('one','DEMO','fee',-1,{})
            store.set('state',{'value':1})
            raise RuntimeError('disk simulation')
    assert store.get('state') is None
    assert store.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0]==0


def test_ledger_duplicate_is_idempotent(tmp_path):
    s=Store(tmp_path)
    assert s.ledger('execution-1','DEMO','fee',-2,{})
    assert not s.ledger('execution-1','DEMO','fee',-2,{})
    assert s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0]==1


def test_round_trip_costs_are_not_double_counted(engine):
    before=engine.equity()
    result=engine.open_signal(make_signal(engine))
    assert result['ok']
    p=engine.state['positions'][0]
    assert p['planned_risk']<=before*.005+1e-6
    result=engine.close_position(p['id'])
    assert result['ok']
    trade=engine.state['closed'][-1]
    assert trade['net']==pytest.approx(trade['gross']-trade['fees']+trade['funding'])
    assert engine.equity()-before==pytest.approx(trade['net'])
    assert engine.close_position(p['id'])['ok'] is False


def test_spot_inventory_and_cash_reconcile(engine):
    before=engine.equity()
    r=engine.open_signal(make_signal(engine,market='spot'))
    assert r['ok']
    p=engine.state['positions'][0]
    assert engine.state['wallets']['Binance:spot']<2500
    engine.close_position(p['id'])
    assert engine.equity()-before==pytest.approx(engine.state['closed'][-1]['net'])


def test_spot_short_rejected(engine):
    assert not engine.open_signal(make_signal(engine,market='spot',side='short'))['ok']


def test_funding_settlement_is_signed_idempotent_and_reconciles(engine):
    engine.open_signal(make_signal(engine))
    p=engine.state['positions'][0]
    q=engine.quote('Binance','BTCUSDT','futures')
    q['settlements']=[dict(time=time.time(),rate=.0001,mark=q['price'])]
    before=engine.equity()
    engine.apply_funding(q)
    expected=-p['quantity']*q['price']*.0001
    assert engine.equity()-before==pytest.approx(expected)
    engine.apply_funding(q)
    assert engine.equity()-before==pytest.approx(expected)
    assert p['funding']==pytest.approx(expected)
    engine.close_position(p['id'])
    assert engine.state['closed'][-1]['net']==pytest.approx(engine.state['closed'][-1]['gross']-engine.state['closed'][-1]['fees']+expected)


def test_market_ownership_and_stale_prices(engine):
    sig=make_signal(engine)
    assert engine.open_signal(sig)['ok']
    assert not engine.open_signal(sig)['ok']
    other=make_signal(engine,'ETHUSDT')
    engine.quote('Binance','ETHUSDT','futures')['observed']=time.time()-90
    assert not engine.open_signal(other)['ok']


def test_paused_engine_rejects_new_positions(engine):
    engine.state['running']=False
    assert not engine.open_signal(make_signal(engine))['ok']


def test_dynamic_allocation_is_bounded_and_does_not_change_existing_positions(engine):
    engine.state['regimes']={'Binance:BTCUSDT:futures:intraday':{'regime':'volatile','observed':time.time()},
                            'Binance:ETHUSDT:futures:swing':{'regime':'uptrend','observed':time.time()}}
    shares={r['strategy']:r['share'] for r in engine.allocation()}
    assert shares['intraday']==0
    assert shares['swing']<=50
    assert not engine.open_signal(make_signal(engine))['ok']


def test_global_strategy_risk_ceiling(engine):
    engine.settings.risk_profile='balanced'
    engine.settings.trade_risk=.5
    results=[]
    for venue in ('Binance','Bybit'):
        for symbol in ('BTCUSDT','ETHUSDT'):
            results.append(engine.open_signal(make_signal(engine,symbol,venue)))
    risk=sum(p['planned_risk'] for p in engine.state['positions'])
    assert risk<=engine.equity()*.02+1e-6
    assert len(engine.state['positions'])<=4
    assert any(not r['ok'] for r in results)  # per-strategy budget cannot consume all global risk


def test_mode_change_and_live_lock(engine):
    assert not asyncio.run(engine.command('mode',{'mode':'LIVE'}))['ok']
    engine.open_signal(make_signal(engine))
    assert not asyncio.run(engine.command('mode',{'mode':'PAPER'}))['ok']
    engine.close_position(engine.state['positions'][0]['id'])
    assert asyncio.run(engine.command('mode',{'mode':'PAPER'}))['ok']
    assert engine.equity()==10000
    assert engine.state['markets']==[]
    assert not engine.state['running']


def test_restart_pauses_and_preserves_positions(engine):
    opened=engine.open_signal(make_signal(engine))
    value=engine.equity()
    restarted=Engine(engine.store.path)
    assert not restarted.state['running']
    assert restarted.state['positions'][0]['id']==opened['id']
    assert restarted.equity()==pytest.approx(value)


def test_daily_loss_preserved_on_restart(engine):
    engine.state['wallets']['Binance:futures']-=700
    engine.check_positions()
    engine.save()
    assert engine.state['halt'].startswith('Günlük')
    restarted=Engine(engine.store.path)
    assert not asyncio.run(restarted.command('start',{}))['ok']


def test_groups_duplicate_and_unknown_reservations():
    g=GroupMachine('g',1)
    g.fill('buy','x',1)
    g.fill('buy','x',1)
    assert g.legs['buy']['filled']==1
    g.unknown('sell')
    assert g.state=='reconciling' and not g.can_release
    g.fill('sell','y',.6)
    assert g.state=='exposed' and not g.can_release
    g.fill('sell','z',.4)
    assert g.state=='hedged' and g.can_release


def test_oversized_fill_rejected():
    g=GroupMachine('g',1)
    with pytest.raises(ValueError):g.fill('buy','x',2)


def test_scheduled_restrictions_expire():
    events=[{'title':'CPI','scheduled_at':10000,'blackout':True}]
    assert entry_restriction(events,'BTCUSDT',now=10000)
    assert entry_restriction(events,'BTCUSDT',now=13000) is None


def test_headline_alone_cannot_halt_or_close():
    assert entry_restriction([{'title':'hack','candidate_restriction':True,'severity':'critical'}],'BTCUSDT') is None


def test_future_candles_cannot_change_past_features():
    rows=demo_candles(count=1400)
    original=features(rows)
    edited=[dict(r) for r in rows]
    for row in edited[1100:]:
        for key in ('open','high','low','close'): row[key]*=1.4
    changed=features(edited)
    for column in ('fast','slow','atr','signal'):
        np.testing.assert_allclose(original[column].iloc[:1100],changed[column].iloc[:1100],equal_nan=True)


def test_demo_report_never_qualifies_for_live(tmp_path):
    result=run_backtest(dict(strategy='intraday',symbol='BTCUSDT',venue='Binance',market='spot',source='DEMO',months=7,fee_bps=10,slippage_bps=3),str(tmp_path))
    assert result['source']=='DEMO' and not result['eligible']
    assert result['summary']['fees']>=0
    assert all(t['net']==pytest.approx(t['gross']-t['fees']+t['funding']) for t in result['trades'])
    assert all(t['entry_time']<t['time'] for t in result['trades'])
    assert all(t['side']=='long' for t in result['trades'])
    json.dumps(result,allow_nan=False)
