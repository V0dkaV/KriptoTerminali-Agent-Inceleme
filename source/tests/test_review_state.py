import asyncio
import copy
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from engine.core import Engine
from engine.models import Signal
from engine.server import create_app
from engine.chat import ChatService


@pytest.mark.parametrize('kind,payload,fail_key',[
    ('paper_session',dict(balance=500),'settings'),
    ('mode',dict(mode='DEMO'),'state:DEMO'),
    ('reset',{},'state:PAPER'),
    ('risk_profile',dict(profile='safe'),'state:PAPER'),
    ('strategy',dict(id='intraday',enabled=False),'state:PAPER'),
    ('news_restrict',dict(id='test',enabled=True),'state:PAPER'),
])
def test_command_memory_and_database_rollback_together(tmp_path,monkeypatch,kind,payload,fail_key):
    monkeypatch.setenv('KRIPTO_DISABLE_LOCAL_AI','1')
    e=Engine(tmp_path);e.news=[dict(id='test',title='Test',restriction_until=0)]
    e.store.set('news',e.news)
    for mode,state in e.states.items():e.store.set('state:'+mode,state)
    e.save()
    before={key:copy.deepcopy(getattr(e,key)) for key in ('states','mode','settings','enabled','news')}
    sql_before=e.store.db.execute('SELECT key,value FROM kv ORDER BY key').fetchall()
    real=e.store.set
    def failed(key,value):
        if key==fail_key:raise OSError('disk error')
        return real(key,value)
    monkeypatch.setattr(e.store,'set',failed)
    result=asyncio.run(e.command(kind,payload))
    assert not result['ok']
    for key,value in before.items():assert getattr(e,key)==value,key
    assert e.store.db.execute('SELECT key,value FROM kv ORDER BY key').fetchall()==sql_before
    assert e.store.db.execute('SELECT count(*) FROM audit').fetchone()[0]==0


def test_settings_partial_write_failure_restores_monitoring_and_limits(tmp_path,monkeypatch):
    app=create_app(tmp_path,'token');e=app.state.engine
    e.state['markets']=[dict(symbol='ETHUSDT',price=100.)]
    e.state['decisions']={'Binance:ETHUSDT:spot:intraday':dict(symbol='ETHUSDT')}
    e.save()
    before=copy.deepcopy(e.states);old=e.settings.model_dump();real=e.store.set
    def failed(key,value):
        if key=='mode':raise OSError('disk error after settings mutation')
        return real(key,value)
    monkeypatch.setattr(e.store,'set',failed)
    changed={**old,'allowlist':['BTCUSDT'],'leverage':5}
    response=TestClient(app).post('/settings',headers={'Authorization':'Bearer token'},json=changed)
    assert response.status_code==200 and not response.json()['ok']
    assert e.settings.model_dump()==old and e.states==before
    assert e.store.get('settings')==old


def test_backup_includes_latest_models_and_never_waits_on_own_transaction(tmp_path):
    e=Engine(tmp_path);e.controllers={'current':dict(schema=3,latest=dict(version='test-latest'))}
    async def run():return await asyncio.wait_for(e.command('backup',{}),3)
    result=asyncio.run(run());assert result['ok']
    with sqlite3.connect(result['path']) as backup:
        import json
        value=json.loads(backup.execute("SELECT value FROM kv WHERE key='adaptive_controllers'").fetchone()[0])
    assert value==e.controllers


def test_lower_account_leverage_tightens_active_mission_instead_of_rejecting_all_entries(tmp_path,monkeypatch):
    e=Engine(tmp_path);e.settings.leverage=5
    chat=ChatService(e)
    p=chat.mission_plan(dict(capital=100,leverage=5,max_positions=4,duration_hours=24))
    assert asyncio.run(chat.execute(p['action']['id']))['ok']
    e.settings.leverage=2;e.settings.max_positions=2
    limits,reason=e.operations.limits()
    assert not reason and limits['requested_leverage']==2
    current=e.operations.snapshot()['mission']
    assert current['leverage']==5 and current['effective_leverage']==2
    assert current['max_positions']==4 and current['effective_max_positions']==2


def test_closed_groups_must_be_resolved_before_reset(tmp_path):
    e=Engine(tmp_path);e.state['groups']=[dict(id='unknown',status='unknown')]
    initial=e.state['session_id']
    assert not asyncio.run(e.command('reset',{}))['ok']
    assert e.state['session_id']==initial and len(e.state['groups'])==1


def test_old_reports_are_preserved_but_flagged_for_retest(tmp_path):
    app=create_app(tmp_path,'token');e=app.state.engine
    old=dict(id='a'*32,kind='backtest',source='DEMO',summary=dict(net=100))
    new=dict(id='b'*32,kind='backtest',source='DEMO',execution_model='bar-causal-v2',summary=dict(net=-50))
    e.reports=[old,new]
    assert e.report_preview(old)['needs_retest'] and not e.report_preview(new)['needs_retest']
    client=TestClient(app);headers={'Authorization':'Bearer token'}
    result=client.get('/report/'+'a'*32,headers=headers).json()
    assert result['needs_retest'] and result['summary']['net']==100
    assert not client.get('/report/'+'b'*32,headers=headers).json()['needs_retest']


def test_shutdown_prevents_new_risk_and_config_commands(tmp_path):
    e=Engine(tmp_path);e.closing=True
    sig=Signal(strategy='intraday',symbol='BTCUSDT',venue='Binance',market='spot',side='long',price=100,stop=99,target=102,reason='test',candle_time=0)
    assert 'kapanıyor' in e.risk_gate(sig)
    assert not asyncio.run(e.command('start',{}))['ok']
    assert e.operations.validate(dict(capital=100,leverage=2,max_positions=2,duration_hours=24))


def test_legacy_unapproved_experiment_is_quarantined_without_erasing_promoted_model(tmp_path):
    e=Engine(tmp_path)
    e.store.set('adaptive_controllers',{
        'unapproved':dict(schema=3,latest=dict(version='exp1',policy=dict(methods=['squeeze'])),pending=dict(version='exp1')),
        'promoted':dict(schema=3,champion=dict(version='exp2',policy=dict(methods=['breakout'])),latest=dict(version='exp2',policy=dict(methods=['breakout'])))})
    upgraded=Engine(tmp_path)
    assert 'latest' not in upgraded.controllers['unapproved']
    assert upgraded.controllers['unapproved']['pending']['version']=='exp1'
    assert upgraded.controllers['promoted']['champion']['version']=='exp2'
    assert upgraded.store.get('adaptive_controllers')==upgraded.controllers


def test_background_fault_pauses_entries_instead_of_silently_losing_control_loop(tmp_path,monkeypatch):
    import engine.core as core
    e=Engine(tmp_path);e.state['running']=True
    async def failed():raise OSError('test fault without exposing exception text')
    async def idle(*args):await asyncio.Event().wait()
    monkeypatch.setattr(e,'heartbeat',failed)
    for name in ('prices','scan','dispatch_entries','news_loop','local_ai_loop'):monkeypatch.setattr(e,name,idle)
    monkeypatch.setattr(e.training,'run',idle);monkeypatch.setattr(core,'listen',idle)
    async def run():
        await e.start()
        async def halted():
            while not e.state['halt']:await asyncio.sleep(.005)
        await asyncio.wait_for(halted(),2)
        assert not e.state['running'] and 'pozisyon kontrolü' in e.state['halt']
        await asyncio.sleep(.01)
        assert e.store.get('state:PAPER')['halt']==e.state['halt']
        assert 'test fault' not in e.store.audit_list('PAPER')[0]['message']
        await e.stop()
    asyncio.run(run())
    restarted=Engine(tmp_path)
    assert not restarted.state['running'] and not restarted.state['halt']
