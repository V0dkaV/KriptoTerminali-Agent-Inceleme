import asyncio
import math
import time
import pytest
from pydantic import ValidationError
from engine.core import Engine
from engine.models import RiskSettings,Signal
from engine.portfolio import DEFAULT_SYMBOLS,PROFILES,correlation,concentration,style
from engine.market import Exchange
from engine.stream import subscription_batches


def signal(symbol='SOLUSDT',**kwargs):
    return Signal(strategy='intraday',symbol=symbol,venue='Binance',market='futures',side='long',
                  price=100,stop=99,target=102,candle_time=int(time.time()//900)*900-900,reason='test',**kwargs)


def test_profiles_switch_without_reset_or_resizing(tmp_path):
    e=Engine(tmp_path)
    e.state['wallets']={k:250 for k in e.state['wallets']}
    for profile,p in PROFILES.items():
        assert asyncio.run(e.command('risk_profile',{'profile':profile}))['ok']
        assert e.settings.max_positions==p['max_positions']
        assert e.equity()==1000
        assert e.settings.trade_risk==p['trade_risk']
    assert not asyncio.run(e.command('risk_profile',{'profile':'unlimited'}))['ok']


def test_expansion_migrates_original_default_keeps_balance_and_custom_limits(tmp_path):
    e=Engine(tmp_path)
    e.store.set('universe_v4',False)
    old=e.settings.model_dump()
    for k in ('risk_profile','symbol_risk','correlated_risk'):old.pop(k)
    old.update(trade_risk=.5,max_positions=4,allowlist=['BTCUSDT','ETHUSDT'],paper_balance=1000)
    e.store.set('settings',old)
    account=e.new_state('PAPER')
    account.update(wallets={k:250 for k in account['wallets']},initial=1000,peak=1000,day_equity=1000)
    e.store.set('state:PAPER',account)
    upgraded=Engine(tmp_path)
    assert upgraded.equity()==1000 and upgraded.state['initial']==1000
    assert upgraded.settings.allowlist==DEFAULT_SYMBOLS and upgraded.settings.max_positions==8
    # Subsequent launches must not undo a user's smaller list or limits.
    upgraded.settings.allowlist=['SOLUSDT']
    upgraded.settings.max_positions=2
    upgraded.store.set('settings',upgraded.settings.model_dump())
    again=Engine(tmp_path)
    assert again.settings.allowlist==['SOLUSDT'] and again.settings.max_positions==2


def test_mixed_risk_requires_actual_success_not_just_model_confidence():
    s=RiskSettings()
    assert style(s,signal(model_score=.99,risk_multiplier=.25),[])[0]=='safe'
    actual=[dict(r=1.,method='breakout') for _ in range(5)]
    assert style(s,signal(model_score=.7,risk_multiplier=1),actual)==('aggressive',1.)
    assert style(s,signal(model_score=.7,risk_multiplier=1),[dict(r=-1.,method='breakout')]*5)[0]=='balanced'


def test_fresh_price_cannot_bypass_liquidity_filter(tmp_path):
    e=Engine(tmp_path);e.state['running']=True
    q=dict(symbol='SOLUSDT',venue='Binance',market='futures',price=100,bid=99.99,ask=100.01,
           volume=4_999_999,observed=time.time(),mark_price=100,mark_price_observed=time.time())
    e.state['markets']=[q]
    assert 'likidite' in e.risk_gate(signal()).lower()


def test_unknown_and_observed_correlations_share_budget():
    s=RiskSettings()
    p=[dict(symbol='BTCUSDT',planned_risk=10)]
    remaining,info=concentration(s,signal(),p,1000,{})
    assert remaining==pytest.approx(.25) and info['unknown']==1
    a={i:math.sin(i) for i in range(60)}
    b={i:math.cos(i*.7) for i in range(60)}
    assert correlation(a,a)==pytest.approx(1)
    remaining,info=concentration(s,signal(),p,1000,{'SOLUSDT':a,'BTCUSDT':b})
    assert remaining==1 and info['unknown']==0
    # Same asset always accumulates across venues and markets.
    assert concentration(s,signal('BTCUSDT'),p,1000,{})[0]==0


def test_many_positions_are_real_but_bounded_across_assets(tmp_path):
    e=Engine(tmp_path);e.mode='DEMO';e.state['running']=True
    asyncio.run(e.command('risk_profile',{'profile':'aggressive'}))
    e.state['markets']=[]
    for symbol in DEFAULT_SYMBOLS:
        e.state['markets'].append(dict(symbol=symbol,venue='Binance',market='futures',price=100,bid=99.99,ask=100.01,observed=time.time()))
    # Small independent risk reservations make the position-count ceiling binding.
    for i,symbol in enumerate(DEFAULT_SYMBOLS[:13]):
        sig=signal(symbol,risk_multiplier=.25)
        sig.stop=95;sig.target=110
        sig.strategy='intraday' if i%2 else 'swing'
        outcome=e.open_signal(sig)
        assert outcome['ok']==(i<12),outcome
    assert len(e.state['positions'])==12
    assert sum(p['planned_risk'] for p in e.state['positions'])<=e.equity()*.025+1e-5


def test_bybit_batches_and_quote_filter(monkeypatch):
    batches=subscription_batches(DEFAULT_SYMBOLS)
    assert all(len(b)<=10 for b in batches) and sum(map(len,batches))==48
    exchange=Exchange('Bybit')
    rows=[dict(symbol='SOLUSDT',lastPrice='100',bid1Price='99.99',ask1Price='100.01',turnover24h='9000000',price24hPcnt='.04',markPrice='100'),
          dict(symbol='UNKNOWNUSDT',lastPrice='1'),dict(symbol='ETHUSDT',lastPrice='10',bid1Price='0',ask1Price='10')]
    monkeypatch.setattr(exchange,'public',lambda *args:dict(result=dict(list=rows)))
    q=exchange.quotes(['SOLUSDT','ETHUSDT'],'futures')
    assert len(q)==1 and q[0]['change']==4 and q[0]['mark_price']==100


def test_symbol_validation_deduplicates_and_caps():
    assert len(DEFAULT_SYMBOLS)==24
    assert RiskSettings(allowlist=['SOLUSDT','SOLUSDT']).allowlist==['SOLUSDT']
    with pytest.raises(ValidationError):RiskSettings(allowlist=['../../abcUSDT'])
    with pytest.raises(ValidationError):RiskSettings(allowlist=[f'T{i}USDT' for i in range(1501)])
