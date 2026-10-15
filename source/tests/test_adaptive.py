import asyncio
import copy
import math
import time

import pytest

from engine.adaptive import (METHODS,SCHEMA,train_candidate,update_controller,decision,select,
    consider_promotion,consider_rollback,register_trials,tick_trials,options,dataset)
from engine.core import Engine
from engine.models import Signal
from engine.research import demo_candles


def model(version='one',qualified=True):
    return dict(schema=SCHEMA,version=version,qualified=qualified,trained_at=1000,candle_time=900,
        samples=100,evaluation_samples=50,coefficients=[0.0]*19,intercept=math.log(4),
        families={m:dict(count=20,mean_r=.3,net_r=6,wins=12,drawdown_r=2) for m in METHODS},
        qualification=dict(count=30,net_r=6,drawdown_r=2),baseline=dict(count=30,net_r=3,drawdown_r=3))


def choice(method='momentum'):
    return dict(method=method,side='long',price=100,stop=98,target=104,candle_time=900,features=[0.0]*19,reason='fixture')


def test_ml_veto_changes_actual_decision_and_does_not_raise_risk():
    low=model();low['intercept']=-10
    assert select(low,[choice()],qualified=True) is None
    selected=select(model(),[choice()],qualified=True)
    assert selected['model_version']=='one'
    assert selected['risk_multiplier']==.25
    assert selected['model_score']>.7


def test_learned_context_selects_different_methods():
    m=model()
    m['coefficients'][10]=2  # momentum method one-hot
    a=choice('breakout');a['features'][9]=1
    b=choice('momentum');b['features'][10]=1
    assert select(m,[a,b])['method']=='momentum'


def test_own_losses_pause_a_method():
    feedback=[dict(method='momentum',r=-.5,closed_at=2000+i) for i in range(5)]
    assert select(model(),[choice()],feedback,now=3000) is None
    assert select(model(),[choice('breakout')],feedback,now=3000) is not None


def test_repeated_holdout_cannot_automatically_replace_a_model():
    controller=update_controller({},model(),now=1100)
    assert controller['champion']['version']=='one'
    controller=update_controller(controller,model('two'),now=1200)
    assert controller['champion']['version']=='one'
    assert controller['pending']['version']=='two'
    empty=update_controller({},model(qualified=False),now=1100)
    empty=update_controller(empty,model('later',qualified=True),now=1200)
    assert 'champion' not in empty  # First bootstrap was already used.


def forward_trials(count=20,candidate_r=.5,opened=1300):
    rows=[]
    for i in range(count):
        base=dict(key='key',opened_at=opened+i*10,closed_at=2000+i*10,market='spot',
                  funding_complete=True,challenger_version='two',champion_version='one')
        rows.append(dict(**base,r=.2,champion_accepted=True,challenger_accepted=False))
        rows.append(dict(**base,r=candidate_r,champion_accepted=False,challenger_accepted=True))
    return rows


def controller_pair():
    c=update_controller({},model(),1100)
    return update_controller(c,model('two'),1200)


def test_only_future_resolved_comparisons_can_promote():
    c=controller_pair()
    assert consider_promotion(c,forward_trials(opened=900),'key',10000) is None
    assert c['champion']['version']=='one'
    assert consider_promotion(c,forward_trials(count=19),'key',10000) is None
    result=consider_promotion(c,forward_trials(),'key',10000)
    assert result['promoted'] and c['champion']['version']=='two'
    assert c['previous']['version']=='one'


def test_worse_model_is_rejected_and_incomplete_funding_is_not_evidence():
    c=controller_pair()
    unresolved=[{**r,'funding_complete':False,'market':'futures'} for r in forward_trials()]
    assert consider_promotion(c,unresolved,'key',10000) is None
    result=consider_promotion(c,forward_trials(candidate_r=-.1),'key',10000)
    assert not result['promoted']
    assert c['champion']['version']=='one' and 'pending' not in c


def test_bad_forward_results_roll_back_to_previous_model():
    c=controller_pair()
    consider_promotion(c,forward_trials(),'key',10000)
    feedback=[dict(model_version='two',r=-.2,closed_at=11000+i) for i in range(20)]
    result=consider_rollback(c,feedback,12000)
    assert result['rollback'] and c['champion']['version']=='one'


def test_trials_have_real_forward_entry_and_costs():
    q=dict(venue='Binance',market='spot',symbol='BTCUSDT',price=100,bid=99.99,ask=100.01,observed=1300)
    s=dict(markets=[q])
    c=controller_pair()
    register_trials(s,'key:intraday',c,[{**choice(),'candle_time':0}],q,[],now=1300)
    assert len(s['adaptive_trials'])==1
    trial=s['adaptive_trials'][0]
    assert trial['entry']>q['ask']
    assert trial['champion_accepted'] and trial['challenger_accepted']
    q.update(price=105,bid=104.99,ask=105.01,observed=1400)
    tick_trials(s,1400)
    assert trial['closed_at']==1400 and trial['r']>0 and trial['funding_complete']
    previous=trial['r']
    tick_trials(s,1500)
    assert trial['r']==previous


def test_stale_or_unclosed_signals_are_not_forward_evidence():
    q=dict(venue='Binance',market='spot',symbol='BTCUSDT',price=100,bid=99.99,ask=100.01,observed=1300)
    s=dict(markets=[q])
    register_trials(s,'key:intraday',controller_pair(),[choice()],q,[],now=1300)
    assert not s.get('adaptive_trials')  # Candle at 900 has not closed at 1300.
    register_trials(s,'key:intraday',controller_pair(),[{**choice(),'candle_time':-5000}],q,[],now=1300)
    assert not s.get('adaptive_trials')


def test_open_paper_trade_records_real_net_feedback_once(tmp_path):
    e=Engine(tmp_path)
    e.state['running']=True
    now=time.time()
    e.state['markets']=[dict(venue='Binance',market='futures',symbol='BTCUSDT',price=80000,bid=79999,ask=80001,
        observed=now,mark_price=80000,mark_price_observed=now,bid_observed=now,ask_observed=now,volume=10000000)]
    e.news_sources=[dict(status='ok',observed=now)]
    sig=Signal(strategy='intraday',symbol='BTCUSDT',venue='Binance',market='futures',side='long',
        price=80000,stop=79000,target=82000,candle_time=int(now//900)*900-900,reason='fixture',
        method='momentum',features=[0.0]*19,risk_multiplier=.25,model_version='one')
    opened=e.open_signal(sig)
    assert opened['ok']
    p=e.state['positions'][0]
    assert p['planned_risk']<=12.5
    assert e.close_position(p['id'])['ok']
    closed=e.state['closed'][-1]
    e.record_feedback(closed)
    records=e.feedback('Binance:BTCUSDT:futures:intraday')
    assert len(records)==1 and records[0]['net']==closed['net']
    assert records[0]['r']==pytest.approx(closed['net']/closed['planned_risk'])
    restarted=Engine(tmp_path)
    assert len(restarted.feedback('Binance:BTCUSDT:futures:intraday'))==1
    assert not restarted.state['running']


def test_training_uses_only_past_outcomes_and_never_spot_shorts():
    rows=demo_candles(count=4000)
    candidate=train_candidate(rows,'intraday','spot')
    changed=copy.deepcopy(rows)
    for row in changed[3000:]:
        for k in ('open','high','low','close'):row[k]*=1.05
    other=train_candidate(changed,'intraday','spot')
    assert candidate['version']==other['version']
    assert candidate['training_end']<candidate['evaluation_start']
    assert all(r['end']<=rows[-1]['time']+900 for r in dataset(rows,'intraday','spot'))
    assert all(c['side']=='long' for c in options(rows,'intraday','spot'))
