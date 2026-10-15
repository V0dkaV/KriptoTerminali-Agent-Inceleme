import asyncio
import copy
import time

import pytest

from engine.chat import ChatService
from engine.core import Engine
from engine.models import Signal


@pytest.fixture
def scoped_engine(tmp_path,monkeypatch):
    monkeypatch.setenv('KRIPTO_DISABLE_LOCAL_AI','1')
    e=Engine(tmp_path)
    e.state['running']=True
    e.settings.local_ai_enabled=False
    now=time.time()
    e.news_sources=[dict(name='test',status='ok',observed=now)]
    e.state['markets']=[dict(symbol='BTCUSDT',venue=v,market=m,price=100.,bid=99.99,ask=100.01,
        mark_price=100.,mark_price_observed=now,volume=10000000.,observed=now,
        price_observed=now,bid_observed=now,ask_observed=now)
        for v,m in [('Binance','spot'),('Bybit','spot'),('Bybit','futures')]]
    for venue,market in [('Binance','spot'),('Bybit','spot'),('Bybit','futures')]:
        signal=Signal(strategy='intraday',symbol='BTCUSDT',venue=venue,market=market,
            side='long',price=100.,stop=99.,target=102.,method='manual',
            candle_time=int(now//900)*900-900,reason='isolated close-scope fixture')
        assert e.open_signal(signal,budget_limit=30,requested_leverage=1,origin='chat')['ok']
    yield e
    e.store.db.close()


async def ask(chat,text):
    assert chat.submit(text)['ok']
    await chat.task
    return chat.snapshot()['messages'][-1]


def test_close_filters_venue_product_side_and_only_closes_requested_position(scoped_engine):
    e=scoped_engine;chat=ChatService(e)
    async def run():
        result=await ask(chat,'Bybit vadeli BTC long pozisyonunu kapat')
        assert len(result['actions'])==1
        action=result['actions'][0]
        assert 'Bybit' in action['summary'] and 'futures' in action['summary']
        assert (await chat.execute(action['id']))['ok']
        assert {(p['venue'],p['market']) for p in e.state['positions']}=={('Binance','spot'),('Bybit','spot')}
    asyncio.run(run())


@pytest.mark.parametrize('message',[
    'BTC ve ETH dışındaki tüm pozisyonları kapat',
    'BTC hariç tüm pozisyonları kapat',
    'XYZ tüm pozisyonları kapat',
    'BTC ve ETH pozisyonlarını kapat',
    'Binance Bybit BTC pozisyonunu kapat',
    'BTC spot vadeli pozisyonunu kapat',
    'BTC long short pozisyonunu kapat',
    'Kârdaki tüm pozisyonları kapat',
    'BTC 3x pozisyonunu kapat',
    'BTC yerine ETH pozisyonunu kapat',
])
def test_unsupported_close_scopes_never_become_close_all(scoped_engine,message):
    before=copy.deepcopy(scoped_engine.state)
    result=asyncio.run(ask(ChatService(scoped_engine),message))
    assert not result['actions']
    assert scoped_engine.state==before


@pytest.mark.parametrize('message,count',[
    ('Tüm pozisyonları kapat',3),
    ('Bybit tüm pozisyonları kapat',2),
    ('Tüm spot pozisyonları kapat',2),
    ("Binance'deki BTC pozisyonunu kapat",1),
    ('Bitcoin pozisyonunu kapat',3),
    ('Bybit short BTC pozisyonunu kapat',0),
])
def test_supported_scopes_preserve_unambiguous_selection(scoped_engine,message,count):
    result=asyncio.run(ask(ChatService(scoped_engine),message))
    assert len(result['actions'])==count


@pytest.mark.parametrize('message',[
    '100 USDT ile sadece BTC spot piyasasını tara',
    '100 USDT ile Bybit piyasasını tara',
    '100 USDT ile vadeli fırsat ara',
    '100 USDT ile 6 saat piyasayı tara',
    '100 USDT ile 2 pozisyon sınırıyla piyasayı tara',
    '100 USDT ile yüzde 1 riskle piyasayı tara',
    '100 USDT ile agresif piyasayı tara',
    '100 USDT ile BTC hariç piyasayı tara',
    '100 USDT ile sadece long fırsat bul',
])
def test_mission_requests_do_not_discard_unsupported_scope(scoped_engine,message):
    before=copy.deepcopy(scoped_engine.state)
    result=asyncio.run(ask(ChatService(scoped_engine),message))
    assert not result['actions']
    assert scoped_engine.state==before


def test_simple_combined_mission_request_still_proposes_explicit_scope(scoped_engine):
    result=asyncio.run(ask(ChatService(scoped_engine),'100 USDT ile 2x piyasayı tara'))
    assert len(result['actions'])==1 and result['actions'][0]['kind']=='mission'
    assert not scoped_engine.state.get('mission')


@pytest.mark.parametrize('message',[
    'BTC 100 USDT değil 1000 USDT bütçeyle 3x vadeli long işlem aç',
    'BTC 100 USDT ile 2x değil 3x vadeli long işlem aç',
    'BTC 100 USDT ile 2x 3x vadeli long işlem aç',
    'BTC 100 USDT yerine 200 USDT ile vadeli long işlem aç',
    'BTC 100 USDT ile 3x cross vadeli long işlem aç',
    'BTC 100 USDT ile 3x çapraz vadeli long işlem aç',
])
def test_manual_trade_ambiguity_and_cross_margin_rejected_before_data_fetch(scoped_engine,monkeypatch,message):
    def no_fetch(*args):raise AssertionError('ambiguous command must not prepare market data')
    monkeypatch.setattr(scoped_engine,'candles',no_fetch)
    result=asyncio.run(ask(ChatService(scoped_engine),message))
    assert not result['actions'] and result['status']=='done'
    assert 'plan hazırlamadım' in result['content']


def test_shutdown_cannot_be_resumed_by_queued_chat_confirmation(scoped_engine):
    chat=ChatService(scoped_engine)
    async def run():
        response=await ask(chat,'Oturumu sürdür')
        scoped_engine.closing=True
        scoped_engine.state['running']=False
        assert not chat.submit('Hesabımı özetle')['ok']
        assert not (await chat.execute(response['actions'][0]['id']))['ok']
        assert not scoped_engine.state['running']
    asyncio.run(run())
