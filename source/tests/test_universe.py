import asyncio
import copy
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from engine.core import Engine
from engine.market import Exchange
from engine.universe import Universe, PRODUCTS
from engine.server import create_app
from engine.diagnostics import snapshot
from engine import scanner_cache
from engine.portfolio import concentration
from engine.models import Signal


def quote(symbol, volume=10_000_000, **extra):
    now=time.time()
    return dict(symbol=symbol,venue='Binance',market='spot',price=100,bid=99.99,ask=100.01,
        volume=volume,observed=now,price_observed=now,bid_observed=now,ask_observed=now,**extra)


def catalog(names):
    return [(v,m,[dict(symbol=s) for s in names],'') for v,m in PRODUCTS]


def test_rotation_covers_entire_liquid_universe_and_keeps_priority(tmp_path):
    e=Engine(tmp_path);names=[f'T{i}USDT' for i in range(100)]
    e.settings.allowlist=names;e.universe.merge(catalog(names))
    e.state['markets']=[quote(s,100_000_000-i) for i,s in enumerate(names)]
    seen=set()
    for _ in range(9):
        batch=e.universe.batch(e);assert len(batch)==16 and len(batch)==len(set(batch))
        assert batch[:4]==names[:4];seen.update(batch)
    assert seen==set(names)


@pytest.mark.parametrize('change',[dict(volume=100),dict(ask=103),dict(price=float('nan')),dict(bid=101),dict(observed=0,bid_observed=0,ask_observed=0,price_observed=0)])
def test_liquidity_filter_rejects_invalid_stale_or_expensive_quote(change):
    q=quote('BTCUSDT');q.update(change);assert not Universe.liquid(q)


def test_partial_catalog_preserves_cache_but_old_source_cannot_authorize_entry(tmp_path):
    e=Engine(tmp_path);e.universe.merge(catalog(['BTCUSDT']))
    e.universe.sources['Binance:spot']['updated_at']=time.time()-4000
    e.universe.merge([('Binance','spot',[],'unavailable')])
    assert e.universe.supports('Binance','BTCUSDT','spot')
    assert not e.universe.supports('Binance','BTCUSDT','spot',fresh=True)
    assert e.universe.snapshot(e)['status']=='partial'


def test_discovery_preserves_account_mission_limits_and_exposed_coin(tmp_path,monkeypatch):
    e=Engine(tmp_path);e.state['positions']=[dict(symbol='OLDUSDT')]
    e.state['mission']=dict(id='approved',status='paused',capital=50)
    before=copy.deepcopy(e.states);limits=e.settings.model_dump(exclude={'allowlist'})
    monkeypatch.setattr(Exchange,'catalog',lambda *args:[dict(symbol='NEWUSDT')])
    asyncio.run(e.refresh_universe())
    assert set(e.settings.allowlist)=={'OLDUSDT','NEWUSDT'}
    assert e.state['positions']==before['PAPER']['positions'] and e.state['wallets']==before['PAPER']['wallets']
    assert e.state['mission']==before['PAPER']['mission']
    assert e.settings.model_dump(exclude={'allowlist'})==limits


def test_failed_discovery_write_rolls_back_memory_and_database(tmp_path,monkeypatch):
    e=Engine(tmp_path);before=e.settings.model_dump();state=copy.deepcopy(e.states)
    real=e.store.set
    monkeypatch.setattr(Exchange,'catalog',lambda *args:[dict(symbol='NEWUSDT')])
    def fail(key,value):
        if key=='settings':raise OSError('disk')
        return real(key,value)
    monkeypatch.setattr(e.store,'set',fail)
    with pytest.raises(OSError):asyncio.run(e.refresh_universe())
    assert e.settings.model_dump()==before and e.states==state
    assert not e.universe.catalogs and not e.store.get('exchange_universe')


def test_stream_selection_is_bounded_stable_and_keeps_exposed_positions(tmp_path):
    e=Engine(tmp_path);names=[f'T{i}USDT' for i in range(100)]
    e.settings.allowlist=names;e.universe.merge(catalog(names))
    e.state['markets']=[quote(s,100_000_000-i) for i,s in enumerate(names)]
    original=e.universe.streams(e,'Binance','spot');assert len(original)==60
    e.state['markets'].reverse();e.state['markets'][0]['volume']=1_000_000_000
    assert e.universe.streams(e,'Binance','spot')==original
    e.state['positions']=[dict(symbol=names[-1],venue='Binance',market='spot')]
    assert names[-1] in e.universe.streams(e,'Binance','spot')
    assert len(e.universe.streams(e,'Binance','spot'))<=61


def test_manual_catalog_boundary_and_refresh_never_start_account(tmp_path):
    app=create_app(tmp_path,'token');e=app.state.engine
    client=TestClient(app);headers={'Authorization':'Bearer token'}
    body=e.settings.model_dump();body.update(auto_universe=False,allowlist=[f'T{i}USDT' for i in range(61)])
    assert client.post('/settings',headers=headers,json=body).status_code==400
    result=client.post('/universe-refresh',headers=headers).json()
    assert result['ok'] and not e.state['running'] and e.universe.refresh_requested


def test_enabling_auto_after_manual_requests_immediate_discovery(tmp_path):
    app=create_app(tmp_path,'token');e=app.state.engine;e.settings.auto_universe=False
    e.universe.refresh_requested=False
    body=e.settings.model_dump();body['auto_universe']=True
    result=TestClient(app).post('/settings',headers={'Authorization':'Bearer token'},json=body).json()
    assert result['ok'] and e.universe.refresh_requested and not e.state['running']


def test_stale_ui_settings_cannot_shrink_automatic_catalog(tmp_path):
    app=create_app(tmp_path,'token');e=app.state.engine
    e.universe.merge(catalog(['BTCUSDT','NEWUSDT']))
    body=e.settings.model_dump();body['allowlist']=['BTCUSDT']
    result=TestClient(app).post('/settings',headers={'Authorization':'Bearer token'},json=body).json()
    assert result['ok'] and set(e.settings.allowlist)=={'BTCUSDT','NEWUSDT'}


def test_paused_mission_explains_gate_even_with_engine_running(tmp_path):
    e=Engine(tmp_path);e.state['running']=True
    e.state['mission']=dict(status='paused',reason='Uygulama yeniden açıldı.')
    gate=snapshot(e)['entry_gate']
    assert gate['blocked'] and gate['code']=='mission_paused'
    assert 'İşlem merkezi' in gate['message'] and e.state['running']


def test_scanner_history_survives_memory_eviction(tmp_path):
    e=Engine(tmp_path);key=('PAPER','Binance','BTCUSDT','15m','spot')
    rows=[dict(time=900,open=1,high=2,low=.5,close=1.5,volume=10)]
    scanner_cache.save(e,key,rows)
    e.cache={('PAPER','Binance',f'T{i}USDT','15m','spot'):(i,rows) for i in range(250)}
    scanner_cache.trim(e);assert len(e.cache)==192
    assert scanner_cache.load(e,key)[1]==rows


def test_multiplier_alias_requires_independent_spot_underlying_and_shares_risk(tmp_path):
    e=Engine(tmp_path)
    e.universe.merge([('Binance','spot',[dict(symbol='PEPEUSDT'),dict(symbol='1INCHUSDT')],''),
        ('Bybit','futures',[dict(symbol='1000PEPEUSDT'),dict(symbol='1000FAKEUSDT')],'')])
    assert e.universe.canonical('1000PEPEUSDT')=='PEPEUSDT'
    assert e.universe.canonical('1INCHUSDT')=='1INCHUSDT'
    assert e.universe.canonical('1000FAKEUSDT')=='1000FAKEUSDT'
    sig=Signal(strategy='intraday',symbol='1000PEPEUSDT',venue='Bybit',market='futures',side='long',price=100,stop=99,target=102,reason='test',candle_time=900)
    rate,info=concentration(e.settings,sig,[dict(symbol='PEPEUSDT',planned_risk=10)],1000,{},e.universe.aliases())
    assert info['symbol_used']==10 and rate==0


def test_signal_receipt_survives_500_row_window_and_restart(tmp_path,monkeypatch):
    e=Engine(tmp_path);e.state['running']=True
    monkeypatch.setattr(e,'refresh_entry_candidates',lambda:None)
    opened=[];monkeypatch.setattr(e,'open_signal',lambda *args,**kwargs:opened.append(1) or dict(ok=False,message='test veto'))
    sig=Signal(strategy='intraday',symbol='BTCUSDT',venue='Binance',market='futures',side='long',price=100,stop=99,target=102,reason='test',candle_time=int(time.time()//900)*900-900)
    e.operations.publish(sig);e.operations.dispatch();assert len(opened)==1
    e.state['last_signals']=['evicted-'+str(i) for i in range(500)]
    e.state['operation_candidates']={};e.state['operation_journal']=[]
    e.operations.publish(sig);e.operations.dispatch();assert len(opened)==1
    e.save()
    restarted=Engine(tmp_path);restarted.state['running']=True
    monkeypatch.setattr(restarted,'refresh_entry_candidates',lambda:None)
    monkeypatch.setattr(restarted,'open_signal',lambda *args,**kwargs:opened.append(1) or dict(ok=False,message='test veto'))
    restarted.state['operation_candidates']={};restarted.operations.publish(sig);restarted.operations.dispatch()
    assert len(opened)==1


def test_failed_signal_transaction_does_not_leave_receipt(tmp_path,monkeypatch):
    e=Engine(tmp_path);e.state['running']=True
    monkeypatch.setattr(e,'refresh_entry_candidates',lambda:None)
    def fail(*args,**kwargs):raise OSError('disk')
    monkeypatch.setattr(e,'open_signal',fail)
    sig=Signal(strategy='intraday',symbol='BTCUSDT',venue='Binance',market='futures',side='long',price=100,stop=99,target=102,reason='test',candle_time=int(time.time()//900)*900-900)
    e.operations.publish(sig)
    with pytest.raises(OSError):e.operations.dispatch()
    assert not e.store.signal_processed(e.operations.receipt_id(e.operations.identity(sig)))
