import asyncio
import copy
import time

import pytest
from fastapi.testclient import TestClient
from engine.core import Engine
from engine.models import Signal
from engine.chat import ChatService
from engine.server import create_app


@pytest.fixture
def e(tmp_path,monkeypatch):
    monkeypatch.setenv('KRIPTO_DISABLE_LOCAL_AI','1')
    e=Engine(tmp_path)
    e.state['running']=True
    monkeypatch.setattr(e,"refresh_entry_candidates",lambda:None)
    e.settings.local_ai_enabled=False
    now=time.time()
    e.news_sources=[dict(name='test',status='ok',observed=now)]
    e.state['markets']=[dict(symbol=s,venue='Binance',market=m,price=100.,bid=99.99,ask=100.01,
        mark_price=100.,mark_price_observed=now,volume=10000000.,observed=now,price_observed=now,bid_observed=now,ask_observed=now)
        for s in ('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT') for m in ('spot','futures')]
    return e


def signal(symbol='BTCUSDT',score=.8,market='futures'):
    return Signal(strategy='intraday',symbol=symbol,venue='Binance',market=market,side='long',price=100.,stop=99.,target=102.,
                  candle_time=int(time.time()//900)*900-900,reason='test approved signal',model_score=score)


def mission(e,capital=100,**kwargs):
    chat=ChatService(e)
    result=chat.mission_plan(dict(capital=capital,leverage=2,max_positions=3,duration_hours=24,**kwargs))
    assert result['ok'],result
    accepted=asyncio.run(chat.execute(result['action']['id']))
    assert accepted['ok'],accepted
    return chat,result


def test_preview_no_mutation_and_confirmation_receipt(e):
    before=copy.deepcopy(e.state);chat=ChatService(e)
    plan=chat.mission_plan(dict(capital=100,leverage=2,max_positions=3,duration_hours=24))
    assert plan['ok'] and e.state==before
    async def run():return await asyncio.gather(chat.execute(plan['action']['id']),chat.execute(plan['action']['id']))
    first,second=asyncio.run(run());assert first==second and first['ok']
    assert e.state['mission']['capital']==100 and not e.state['positions']
    assert e.state['wallets']==before['wallets']


def test_global_ranking_and_combined_budget(e):
    mission(e)
    e.operations.publish(signal('BTCUSDT',.51))
    e.operations.publish(signal('ETHUSDT',.95))
    e.operations.publish(signal('SOLUSDT',.65))
    e.operations.dispatch()
    positions=e.state['positions'];assert positions and positions[0]['symbol']=='ETHUSDT'
    a=e.operations.accounting(e.state['mission'])
    assert a['used_capital']<=100 and a['open_risk']<=2+1e-7
    assert all(p['planned_risk']<=.75+1e-7 for p in positions)
    assert all(p['mission_id']==e.state['mission']['id'] for p in positions)
    count=len(positions);e.operations.dispatch();assert len(e.state['positions'])==count
    journal=e.operations.snapshot()['decisions'];assert len({j['id'] for j in journal})==len(journal)


@pytest.mark.parametrize('change',['expiry','pause','dayloss','drawdown','disabled','stale','book'])
def test_entry_vetoes_do_not_disable_protective_exits(e,change):
    mission(e)
    if change=='expiry':e.state['mission']['expires_at']=time.time()-1
    elif change=='pause':e.operations.pause()
    elif change=='dayloss':e.state['mission']['day_equity']=110
    elif change=='drawdown':e.state['mission']['peak']=120
    elif change=='disabled':e.enabled['intraday']=False
    elif change=='book':
        for q in e.state['markets']:q['bid_observed']=q['ask_observed']=time.time()-60
    sig=signal()
    if change=='stale':sig.candle_time-=3600
    e.operations.publish(sig);e.operations.dispatch()
    assert not e.state['positions']
    assert e.state['running'] # mission pause affects its entries, not heartbeat


def test_approved_caps_do_not_grow_after_profile_increase(e):
    e.settings.trade_risk=.25;e.settings.total_risk=1;e.settings.daily_loss=1;e.settings.drawdown=6
    mission(e)
    e.settings.trade_risk=.75;e.settings.total_risk=4;e.settings.daily_loss=3;e.settings.drawdown=15
    e.operations.publish(signal());e.operations.dispatch()
    assert e.state['positions'][0]['planned_risk']<=.25+1e-7
    e.state['mission']['day_equity']=102
    e.operations.enforce();assert e.state['mission']['status']=='paused'


def test_restart_and_stopped_mission_cannot_be_bypassed_by_legacy_resume(e):
    mission(e);e.save()
    restarted=Engine(e.store.path)
    assert restarted.state['mission']['status']=='paused' and not restarted.state['running']
    restarted.state['running']=True
    restarted.operations.publish(signal());restarted.operations.dispatch()
    assert not restarted.state['positions']


def test_confirmation_failure_rolls_back_all_account_and_receipt(e,monkeypatch):
    chat=ChatService(e);before=copy.deepcopy(e.state)
    plan=chat.mission_plan(dict(capital=100,leverage=2,max_positions=3,duration_hours=24))
    real=e.store.set
    def failed(key,value):
        if key.startswith('chat_receipt:'):raise OSError('disk error')
        return real(key,value)
    monkeypatch.setattr(e.store,'set',failed)
    result=asyncio.run(chat.execute(plan['action']['id']))
    assert not result['ok'] and e.state==before
    assert e.store.get('state:PAPER',{}).get('mission') is None
    assert not e.store.get('chat_receipt:'+plan['action']['id'])


def test_dispatch_failure_rolls_back_position_journal_and_last_signal(e,monkeypatch):
    mission(e);e.operations.publish(signal());before=copy.deepcopy(e.state)
    monkeypatch.setattr(e,'save',lambda:(_ for _ in ()).throw(OSError('disk error')))
    with pytest.raises(OSError):e.operations.dispatch()
    assert e.state==before
    assert e.store.db.execute("SELECT count(*) FROM ledger WHERE kind='entry_fee'").fetchone()[0]==0


def test_mission_boundaries_rechecked_at_confirmation_and_api_shape(e):
    chat=ChatService(e)
    p=chat.mission_plan(dict(capital=100,leverage=3,max_positions=3,duration_hours=24))
    e.settings.leverage=2
    assert not asyncio.run(chat.execute(p['action']['id']))['ok']
    assert not e.state.get('mission')
    for payload in [dict(capital=20000,leverage=1,max_positions=1,duration_hours=1),dict(capital=100,leverage=6,max_positions=1,duration_hours=1)]:
        assert not chat.mission_plan(payload)['ok']


def test_chat_budget_request_proposes_mission_without_model(e):
    chat=ChatService(e)
    async def run():
        assert chat.submit('100 USDT ile 2x piyasayı tara')['ok']
        await chat.task
    asyncio.run(run())
    result=chat.snapshot()['messages'][-1]
    assert result['kind']=='plan' and result['actions'][0]['kind']=='mission'
    assert not e.state.get('mission')


def test_operations_api_auth_and_strict_payload(tmp_path,monkeypatch):
    monkeypatch.setenv('KRIPTO_DISABLE_LOCAL_AI','1')
    app=create_app(tmp_path,'test-token');client=TestClient(app)
    headers={'Authorization':'Bearer test-token'}
    assert client.get('/operations').status_code==401
    assert client.get('/operations',headers=headers).json()['mode']=='PAPER'
    assert client.post('/operations/plan',headers=headers,json=dict(capital=100,leverage=True,max_positions=1,duration_hours=1)).status_code==422
    result=client.post('/operations/plan',headers=headers,json=dict(capital=100,leverage=2,max_positions=2,duration_hours=24)).json()
    assert result['ok'] and result['action']['kind']=='mission'
