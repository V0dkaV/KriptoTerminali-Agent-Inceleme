import pytest
from fastapi.testclient import TestClient
from engine.server import create_app


@pytest.fixture
def client(tmp_path):
    # No lifespan: unit tests make no background network requests.
    return TestClient(create_app(tmp_path,'t'*64))


def test_local_api_requires_token(client):
    assert client.get('/snapshot').status_code==401
    assert client.post('/command',json={'kind':'start'}).status_code==401


def test_web_origin_is_rejected_even_with_token(client):
    assert client.get('/snapshot',headers={'Authorization':'Bearer '+'t'*64,'Origin':'https://example.com'}).status_code==403


def test_authenticated_snapshot_never_contains_credentials(client):
    response=client.get('/snapshot',headers={'Authorization':'Bearer '+'t'*64})
    assert response.status_code==200
    data=response.json()
    assert data['mode']=='PAPER'
    assert data['live_gate']['allowed'] is False
    assert 'secret' not in response.text


def test_unknown_symbol_and_invalid_limits_fail(client):
    headers={'Authorization':'Bearer '+'t'*64}
    assert client.get('/candles?symbol=../../BTC',headers=headers).status_code==400
    assert client.post('/jobs',headers=headers,json={'months':0}).status_code==422
    assert client.post('/settings',headers=headers,json={'leverage':25}).status_code==422


def test_ai_without_budget_never_calls_provider(client):
    response=client.post('/research-proposal',headers={'Authorization':'Bearer '+'t'*64},json={'prompt':'test'})
    assert response.status_code==200
    assert not response.json()['ok']


def test_reset_isolated_ledgers(client):
    headers={'Authorization':'Bearer '+'t'*64}
    assert client.post('/command',headers=headers,json={'kind':'mode','payload':{'mode':'PAPER'}}).json()['ok']
    data=client.get('/snapshot',headers=headers).json()
    assert data['metrics']['equity']==10000
    assert data['closed']==[]
    assert data['curve']==[]
    assert data['mode']=='PAPER'


def test_open_coin_cannot_be_removed_from_price_monitor(client):
    engine=client.app.state.engine
    engine.state['positions']=[{'symbol':'ETHUSDT'}]
    body=engine.settings.model_dump()
    body['allowlist']=['BTCUSDT']
    response=client.post('/settings',headers={'Authorization':'Bearer '+'t'*64},json=body)
    assert response.status_code==400
    assert 'ETHUSDT' in engine.settings.allowlist


def test_quote_requires_authentication_and_valid_market(client):
    assert client.get('/quote').status_code==401
    headers={'Authorization':'Bearer '+'t'*64}
    assert client.get('/quote?symbol=../../BAD',headers=headers).status_code==400
    assert client.get('/quote?venue=unknown',headers=headers).status_code==400


def test_small_quote_endpoint_preserves_price_timestamp(client):
    e=client.app.state.engine
    q=dict(venue='Binance',symbol='BTCUSDT',market='spot',price=80210.28,price_observed=123,observed=123,price_transport='websocket')
    e.state['markets']=[q]
    body=client.get('/quote',headers={'Authorization':'Bearer '+'t'*64}).json()
    assert body['quote']==q and body['mode']=='PAPER'
    assert 'settings' not in body and 'learning' not in body
