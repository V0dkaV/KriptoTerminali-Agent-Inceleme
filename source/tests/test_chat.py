import asyncio
import copy
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from engine.chat import ChatService,normalized,symbol_in
from engine.core import Engine
from engine.models import Signal
from engine.local_ai import LocalAI
from engine.server import create_app


@pytest.fixture
def engine(tmp_path,monkeypatch):
    monkeypatch.setenv('KRIPTO_DISABLE_LOCAL_AI','1')
    e=Engine(tmp_path)
    e.state['running']=True
    now=time.time()
    e.news_sources=[dict(name='test',status='ok',observed=now)]
    e.settings.local_ai_enabled=False
    e.state['markets']=[dict(symbol='BTCUSDT',venue='Binance',market=market,price=100.,bid=99.99,ask=100.01,
                            mark_price=100.,mark_price_observed=now,volume=10000000.,observed=now,
                            price_observed=now,bid_observed=now,ask_observed=now) for market in ('spot','futures')]
    start=int(now//900)*900-180*900
    rows=[dict(time=start+i*900,open=100.,high=100.25,low=99.75,close=100.,volume=100.) for i in range(180)]
    monkeypatch.setattr(e,'candles',lambda *args:rows)
    return e


async def ask(chat,text):
    result=chat.submit(text)
    assert result['ok']
    await chat.task
    return chat.snapshot()['messages'][-1]


def test_turkish_normalization_and_unambiguous_symbol():
    assert normalized('İŞLEMLERİMİ ÖZETLE')=='islemlerimi ozetle'
    assert symbol_in("BTC'de işlem",['BTCUSDT','ETHUSDT'])=='BTCUSDT'
    assert symbol_in('BTC veya ETH',['BTCUSDT','ETHUSDT']) is None


def test_factual_conversation_never_calls_model_or_changes_account(engine):
    chat=ChatService(engine)
    before=copy.deepcopy(engine.state)
    async def scenario():
        result=await ask(chat,'Hesabımı özetle')
        assert result['kind']=='records' and '10.000,00' in result['content']
        result=await ask(chat,'Son işlemlerimi özetle')
        assert 'Henüz kapanmış işlem yok' in result['content']
        result=await ask(chat,'Neden işlem açmadın?')
        assert 'Henüz tamamlanmış analiz' in result['content']
    asyncio.run(scenario())
    assert engine.state==before


def test_proposal_confirmation_atomic_idempotent_and_restart_safe(engine):
    chat=ChatService(engine)
    async def scenario():
        result=await ask(chat,'Yeni girişleri durdur')
        assert engine.state['running']
        action=result['actions'][0]
        one,two=await asyncio.gather(chat.execute(action['id']),chat.execute(action['id']))
        assert one==two and one['ok'] and not engine.state['running']
        assert len([a for a in engine.store.audit_list('PAPER') if a['kind']=='chat_command'])==1
        restarted=ChatService(engine)
        assert await restarted.execute(action['id'])==one
        result=await ask(restarted,'Oturumu sürdür')
        assert not engine.state['running']
        assert (await restarted.execute(result['actions'][0]['id']))['ok']
        assert engine.state['running']
    asyncio.run(scenario())


@pytest.mark.parametrize('change',['expiry','session','mode','restart'])
def test_old_plans_cannot_mutate_replaced_state(engine,change):
    chat=ChatService(engine)
    async def scenario():
        result=await ask(chat,'Yeni girişleri durdur');action=result['actions'][0]
        if change=='expiry':chat.plans[-1]['expires_at']=time.time()-1
        elif change=='session':engine.state['session_id']='replacement'
        elif change=='mode':engine.mode='DEMO'
        else:chat2=ChatService(engine);return await chat2.execute(action['id'])
        return await chat.execute(action['id'])
    assert not asyncio.run(scenario())['ok']
    assert engine.states['PAPER']['running']


def test_manual_plan_budget_leverage_preview_and_feedback_isolation(engine):
    chat=ChatService(engine)
    async def scenario():
        before=copy.deepcopy(engine.state)
        answer=await ask(chat,'BTC 100 USDT bütçeyle 2x vadeli long işlem aç')
        assert answer['actions'] and engine.state==before
        p=chat.plans[-1];assert p['payload']['preview']['capital_required']<=100
        assert p['payload']['preview']['leverage']==2
        assert (await chat.execute(p['id']))['ok']
        opened=engine.state['positions'][0]
        assert opened['origin']=='chat' and opened['method']=='manual' and opened['leverage']==2
        assert opened['initial_margin']+opened['entry_fee']<=100
        assert engine.close_position(opened['id'])['ok']
        assert not engine.store.get('adaptive_feedback',[])
    asyncio.run(scenario())


@pytest.mark.parametrize('change',['pause','stale_book','lower_leverage','drift','news','drawdown'])
def test_confirmation_rechecks_changed_risk_and_market_conditions(engine,change):
    chat=ChatService(engine)
    async def scenario():
        result=await ask(chat,'BTC 100 USDT bütçeyle 3x vadeli long işlem aç')
        assert result['actions']
        if change=='pause':engine.state['running']=False
        elif change=='stale_book':engine.state['markets'][1]['bid_observed']=time.time()-60
        elif change=='lower_leverage':engine.settings.leverage=1
        elif change=='drift':engine.state['markets'][1].update(price=101,bid=100.99,ask=101.01)
        elif change=='news':engine.news_sources=[]
        else:engine.state['halt']='Hesap düşüşü sınırı'
        return await chat.execute(result['actions'][0]['id'])
    assert not asyncio.run(scenario())['ok']
    assert not engine.state['positions']


def test_non_action_analysis_and_missing_model_explain_without_execution(engine):
    chat=ChatService(engine)
    async def scenario():
        result=await ask(chat,'BTC vadeli piyasa analizi yap')
        assert result['kind']=='analysis' and 'RSI14' in result['content']
        result=await ask(chat,'Merhaba, ne yapabiliyorsun?')
        assert result['kind']=='unavailable'
        result=await ask(chat,'BTC 100 USDT ile 5x vadeli long işlem aç')
        assert '3x tavanını' in result['content'] and not result['actions']
        result=await ask(chat,'100 dolar ile vadeli işlem yap')
        assert 'coin' in result['content'] and not result['actions']
    asyncio.run(scenario())
    assert not engine.state['positions']


@pytest.mark.parametrize('message',[
    'BTC pozisyonunu kapat dersem ne olur?',
    'BTC 100 USDT 3x vadeli long işlem aç demek ne anlama geliyor?',
    'Eğer fiyat düşerse BTC 100 USDT 3x vadeli long işlem aç',
    'BTC 100 USDT 3x spot long işlem aç',
    'BTC 100 USDT 3x vadeli long short işlem aç',
    'BTC 100 USDT 3x vadeli long stop 90 işlem aç'])
def test_hypothetical_or_ambiguous_instructions_never_produce_executable_plans(engine,message):
    chat=ChatService(engine)
    async def scenario():return await ask(chat,message)
    assert not asyncio.run(scenario())['actions']
    assert not engine.state['positions']


def test_receipt_write_failure_rolls_back_account_and_plan(engine,monkeypatch):
    chat=ChatService(engine)
    original=engine.store.set
    def fail(key,value):
        if key.startswith('chat_receipt:'):raise OSError('disk failure')
        return original(key,value)
    async def scenario():
        result=await ask(chat,'BTC 100 USDT bütçeyle 2x vadeli long işlem aç')
        monkeypatch.setattr(engine.store,'set',fail)
        assert not (await chat.execute(result['actions'][0]['id']))['ok']
        assert chat.plans[-1]['status']=='proposed'
    asyncio.run(scenario())
    assert not engine.state['positions'] and not engine.store.db.execute("SELECT id FROM ledger WHERE kind='entry_fee'").fetchall()


def test_chat_api_auth_schema_and_no_arbitrary_action(tmp_path,monkeypatch):
    monkeypatch.setenv('KRIPTO_DISABLE_LOCAL_AI','1')
    app=create_app(tmp_path,'testtoken')
    client=TestClient(app)
    assert client.get('/chat').status_code==401
    headers={'Authorization':'Bearer testtoken'}
    assert client.get('/chat',headers=headers).status_code==200
    assert client.post('/chat',headers=headers,json={'message':'x'*2001}).status_code==422
    assert client.post('/chat/action',headers=headers,json={'id':'code','signal':{}}).status_code==422
    assert not client.post('/chat/action',headers=headers,json={'id':'a'*32}).json()['ok']


def test_chat_model_receives_bounded_facts_and_source_context(engine,monkeypatch):
    engine.settings.local_ai_enabled=True;engine.local_ai.disabled=False
    monkeypatch.setattr(LocalAI,'available',property(lambda self:True))
    captured=[]
    def infer(payload):captured.append(payload);return dict(answer='Verilen bağlamda yalnız sınırlı araştırma yapabilirim.',knowledge_ids=[])
    monkeypatch.setattr(engine.local_ai,'converse',infer)
    chat=ChatService(engine)
    async def scenario():return await ask(chat,'Merhaba, yöntemleri nasıl karşılaştırıyorsun?')
    result=asyncio.run(scenario())
    assert result['kind']=='ai' and captured[0]['facts']['mode']=='PAPER'
    assert len(captured[0]['knowledge']['cards'])==5
    assert 'credentials' not in json.dumps(captured[0]) and not result['actions']
