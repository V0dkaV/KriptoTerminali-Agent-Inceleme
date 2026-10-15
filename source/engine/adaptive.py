"""Bounded paper strategy selection, outcome learning and prospective model trials.

All methods are fixed, reviewable templates. Models may select/veto entries and
reduce their risk; they cannot change portfolio limits or issue exchange orders.
"""
from __future__ import annotations

import hashlib
import math
import time
import uuid
from collections import defaultdict

import numpy as np
from sklearn.linear_model import LogisticRegression

from engine.research import features, recent_contiguous

METHODS={'breakout':'Kanal kırılımı','momentum':'Momentum', 'pullback':'Trend içi geri çekilme',
         'reversion':'Ortalamaya dönüş','squeeze':'Sıkışma kırılımı'}
SCHEMA=3
SCORE_THRESHOLD=.45  # Fixed before evaluation; never tuned on a holdout result.


def frame(rows,strategy,market):
    df=features(rows,strategy)
    c=df.close
    ema=c.ewm(span=20,adjust=False).mean()
    macd=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    hist=macd-macd.ewm(span=9,adjust=False).mean()
    mean=c.rolling(20).mean()
    std=c.rolling(20).std().replace(0,np.nan)
    z=(c-mean)/std
    delta=c.diff()
    gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    rsi=100-100/(1+gain/loss.replace(0,1e-12))
    up=df.fast>df.slow
    down=df.fast<df.slow
    previous=c.shift(1)
    rules={
        'breakout':df.signal.to_numpy(dtype=int),
        'momentum':np.select([up&(hist>0)&(hist.shift(1)<=0)&(rsi>50),down&(hist<0)&(hist.shift(1)>=0)&(rsi<50)],[1,-1],0),
        'pullback':np.select([up&(previous<=ema.shift(1))&(c>ema),down&(previous>=ema.shift(1))&(c<ema)],[1,-1],0),
        'reversion':np.select([(df.trend_strength.abs()<.01)&(z.shift(1)<-2)&(z>-2)&(rsi<45),
                               (df.trend_strength.abs()<.01)&(z.shift(1)>2)&(z<2)&(rsi>55)],[1,-1],0),
        'squeeze':np.select([up&(std.shift(1)/mean.shift(1)<(std/mean).rolling(80).quantile(.35).shift(1))&(c>df.high.rolling(10).max().shift(1)),
                            down&(std.shift(1)/mean.shift(1)<(std/mean).rolling(80).quantile(.35).shift(1))&(c<df.low.rolling(10).min().shift(1))],[1,-1],0)}
    ready=np.isfinite(df.fast)&np.isfinite(df.slow)&np.isfinite(df.atr)&(df.atr>0)&(df.atr/c<.025)
    for name in rules:
        rules[name]=np.where(ready,rules[name],0)
        if market=='spot':rules[name]=np.maximum(0,rules[name])
    df['rsi'],df['z'],df['hist']=rsi.fillna(50),z.fillna(0),hist.fillna(0)
    return df,rules


def vector(row,method,side):
    base=[float(row.momentum)*100*side,float(row.volatility)*100,
          math.log1p(max(0,min(20,float(row.volume_ratio)))),float(row.trend_strength)*100*side,
          float(row.z)*side,float(row.rsi)/100,float(row['hist'])/float(row.close)*100*side,
          float(row.atr)/float(row.close)*100,side]
    one=[float(name==method) for name in METHODS]
    values=base+one+[v*base[3] for v in one]
    return [float(np.clip(v,-10,10)) if math.isfinite(v) else 0.0 for v in values]


def options(rows,strategy,market):
    if not recent_contiguous(rows, strategy):return []
    df,rules=frame(rows,strategy,market)
    r=df.iloc[-1]
    distance=float(r.atr)*(2 if strategy=='intraday' else 3)
    found=[]
    for method,signals in rules.items():
        side=int(signals[-1])
        if not side:continue
        found.append(dict(method=method,side='long' if side>0 else 'short',price=float(r.close),
                          stop=float(r.close)-side*distance,target=float(r.close)+side*2*distance,
                          candle_time=int(r.time),features=vector(r,method,side),
                          reason=METHODS[method]+' · kapanmış mum · öğrenen yöntem seçimi.'))
    return found


def dataset(rows,strategy,market):
    df,rules=frame(rows,strategy,market)
    data=df.to_dict('records')
    horizon=16 if strategy=='intraday' else 42
    step=900 if strategy=='intraday' else 14400
    fee=.001 if market=='spot' else .0006
    samples=[]
    for method,signals in rules.items():
        free=0
        for i in np.flatnonzero(signals):
            if i<free or i+1>=len(data):continue
            r=data[i];side=int(signals[i]);start=i+1
            if data[start]['time'] != r['time'] + step:continue
            entry=data[start]['open']*(1+side*.0003)
            distance=r['atr']*(2 if strategy=='intraday' else 3)
            stop=entry-side*distance;target=entry+side*2*distance
            end=None;exit_price=None
            for j in range(start,min(len(data),start+horizon)):
                b=data[j]
                if b['time'] != r['time'] + (j-i)*step:break
                if side*(b['open']-stop)<=0:exit_price=b['open'];end=j;break
                if (side>0 and b['low']<=stop) or (side<0 and b['high']>=stop):exit_price=stop;end=j;break
                if side*(b['open']-target)>=0:exit_price=b['open'];end=j;break
                if (side>0 and b['high']>=target) or (side<0 and b['low']<=target):exit_price=target;end=j;break
                if j==start+horizon-1:exit_price=b['close'];end=j
            if end is None:continue  # Open labels never enter training.
            exit_price*=1-side*.0003
            # Adverse carrying-cost allowance, explicitly estimated. Forward trials
            # and actual paper feedback below use observed signed funding instead.
            carrying=entry*.0003*(data[end]['time']+step-data[start]['time'])/28800 if market=='futures' else 0
            net=(exit_price-entry)*side-(entry+exit_price)*fee-carrying
            unit=distance+entry*(fee+.0003)*2
            samples.append(dict(id=f'{method}:{int(r["time"])}',method=method,features=vector(df.iloc[i],method,side),
                                time=int(data[start]['time']),end=int(data[end]['time'])+step,r=float(net/unit)))
            free=end+1
    return sorted(samples,key=lambda r:(r['time'],r['method']))


def predict(model,x):
    if not model or not model.get('coefficients'):return None
    z=float(np.dot(model['coefficients'],x)+model['intercept'])
    return 1/(1+math.exp(-max(-35,min(35,z))))


def stats(records):
    ordered=sorted(records,key=lambda t:t.get('closed_at',t.get('end',t.get('time',0))))
    values=[float(t['r']) for t in ordered]
    curve=np.cumsum([0]+values);peak=np.maximum.accumulate(curve)
    return dict(count=len(values),net_r=float(sum(values)),mean_r=float(np.mean(values)) if values else 0,
                drawdown_r=float(np.max(peak-curve)),wins=sum(v>0 for v in values))


def family_state(model,method,feedback,now):
    prior=model.get('families',{}).get(method,{}) if model else {}
    actual=[t for t in feedback if t['method']==method and t.get('closed_at',0)<=now][-30:]
    n=min(20,prior.get('count',0))
    mean=(n*prior.get('mean_r',0)+sum(t['r'] for t in actual)*3)/(n+len(actual)*3+5)
    recent=actual[-5:]
    paused=len(recent)==5 and sum(t['r'] for t in recent)<-1.5 and now-recent[-1]['closed_at']<86400
    return dict(method=method,name=METHODS[method],history_count=prior.get('count',0),
                feedback_count=len(actual),expected_r=mean,paused=paused,
                eligible=prior.get('count',0)>=8 or len(actual)>=5,
                risk_multiplier=.25 if len(actual)<5 else .5 if sum(t['r'] for t in recent)<0 else 1.0)


def select(model,choices,feedback=(),now=None,qualified=True):
    now=now or time.time()
    ranked=[]
    for item in choices:
        if model and item['method'] not in model.get('policy',{}).get('methods',METHODS):continue
        family=family_state(model,item['method'],feedback,now)
        score=predict(model,item['features'])
        if not family['eligible'] or family['paused']:continue
        if qualified and score is not None:
            if score<model.get('policy',{}).get('minimum_score',SCORE_THRESHOLD):continue
            rank=score+family['expected_r']*.25
        else:
            if family['expected_r']<=0:continue
            rank=family['expected_r']
        ranked.append((rank,item,score,family))
    if not ranked:return None
    _,item,score,family=max(ranked,key=lambda r:(r[0],r[1]['method']))
    return {**item,'model_score':score,'risk_multiplier':min(family['risk_multiplier'],1 if qualified else .25),
            'model_version':model.get('version','statistical') if model else 'statistical'}


def evaluate(model,records,baseline=False):
    buckets=defaultdict(list)
    for r in records:buckets[r['time']].append(r)
    selected=[];free=0
    for stamp,items in sorted(buckets.items()):
        if stamp<free:continue
        if baseline:pick=next((r for r in items if r['method']=='breakout'),None)
        else:
            chosen=select(model,items,qualified=True,now=stamp)
            pick=next((r for r in items if chosen and r['id']==chosen['id']),None)
        if pick:selected.append(pick);free=pick['end']
    return stats(selected)


def train_candidate(rows,strategy,market,feedback=(),proposal=None):
    samples=dataset(rows,strategy,market)
    step=900 if strategy=='intraday' else 14400
    boundary=int(rows[int(len(rows)*.7)]['time'])
    training=[r for r in samples if r['end']<boundary]
    holdout=[r for r in samples if r['time']>=boundary]
    # Actual resolved trades replace matching historical approximations only when
    # their entire outcome is before the training boundary. Recent feedback also
    # affects the live Bayesian family score immediately, outside this classifier.
    by_id={r['id']:r for r in training}
    for r in feedback:
        if r.get('closed_at',float('inf'))<boundary and len(r.get('features',[]))==19:
            by_id[f'{r["method"]}:{r["candle_time"]}']=dict(id=r['id'],method=r['method'],features=r['features'],
                time=r['opened_at'],end=r['closed_at'],r=r['r'])
    training=list(by_id.values())
    model=dict(schema=SCHEMA,trained_at=time.time(),candle_time=rows[-1]['time'],samples=len(training),
               evaluation_samples=len(holdout),training_end=max((r['end'] for r in training),default=0),
               evaluation_start=boundary,estimated_history_costs=True,families={},qualified=False,
               feedback_count=len(feedback),note='Sanal hesapta aktif yöntem seçimi; model yalnız kabul ölçütleriyle yükseltilir.')
    for method in METHODS:model['families'][method]=stats([r for r in training if r['method']==method])
    if proposal:
        from engine.local_ai import Experiment
        experiment=Experiment.model_validate(proposal)
        model['policy']=dict(methods=experiment.methods,minimum_score=experiment.minimum_score)
        model['hypothesis']=experiment.hypothesis
    y=np.array([r['r']>0 for r in training],dtype=int)
    if len(training)>=40 and len(np.unique(y))==2 and min(np.bincount(y))>=5:
        fitted=LogisticRegression(C=.5,max_iter=500,random_state=73).fit([r['features'] for r in training],y)
        model.update(coefficients=fitted.coef_[0].tolist(),intercept=float(fitted.intercept_[0]))
    signature=str((model.get('coefficients'),model.get('intercept'),model['families'],model.get('policy'))).encode()
    model['version']=hashlib.sha256(signature).hexdigest()[:12]
    candidate=evaluate(model,holdout)
    baseline=evaluate(model,holdout,baseline=True)
    model.update(qualification=candidate,baseline=baseline)
    model['qualified']=bool(model.get('coefficients') and candidate['count']>=20 and candidate['net_r']>0
                            and candidate['net_r']>baseline['net_r']+.1
                            and candidate['drawdown_r']<=max(3,baseline['drawdown_r']))
    return model


def update_controller(old,candidate,now=None):
    now=now or time.time()
    state=old if old.get('schema')==SCHEMA else dict(schema=SCHEMA,history=[],promotions=0)
    state['latest']=candidate
    if not state.get('bootstrap_done') and candidate['qualified']:
        state.update(champion=candidate,status='active',activated_at=now,promotions=state['promotions']+1,
                     message='İlk model kronolojik maliyetli kabulü geçti; sanal giriş seçimi etkin.')
    elif not state.get('pending') and candidate.get('coefficients') and candidate['version']!=state.get('champion',{}).get('version'):
        state['pending']=candidate
        state['pending_since']=now
    elif candidate.get('policy') and candidate['version']!=state.get('pending',{}).get('version'):
        queue=[r for r in state.get('queue',[]) if r['version']!=candidate['version']]
        state['queue']=(queue+[candidate])[-3:]
    state.setdefault('status','statistical')
    state.setdefault('message','Öğrenen istatistiksel seçici etkin; ML adayı ileri dönem karşılaştırmasında.')
    state['bootstrap_done']=True
    return state


def decision(controller,choices,feedback,now=None):
    model=controller.get('champion') or controller.get('latest') or {}
    qualified=bool(controller.get('champion'))
    result=select(model,choices,feedback,now,qualified)
    if result:
        result['reason']+=f' {"ML" if qualified else "İstatistiksel"} seçici {result["model_version"]}; risk çarpanı {result["risk_multiplier"]:.2f}.'
    return result


def register_trials(state,key,controller,choices,quote,feedback,now=None):
    now=now or time.time()
    if not quote or any(not quote.get(k) for k in ('bid','ask','price')) or now-quote.get('observed',0)>15:return
    if any(now-quote.get(k+'_observed',quote['observed'])>15 for k in ('bid','ask')):return
    records=state.setdefault('adaptive_trials',[])
    active=decision(controller,choices,feedback,now)
    challenger=select(controller.get('pending'),choices,feedback,now,True) if controller.get('pending') else None
    current_version=controller.get('champion',{}).get('version','statistical')
    pending_version=controller.get('pending',{}).get('version','')
    for item in choices:
        step=900 if key.endswith('intraday') else 14400
        if item['candle_time']+step>now or now-item['candle_time']-step>step+60:continue
        identity=f'{key}:{item["method"]}:{item["candle_time"]}'
        if any(t['id']==identity for t in records):continue
        if any(t['key']==key and t['method']==item['method'] and not t.get('closed_at') for t in records):continue
        side=1 if item['side']=='long' else -1
        entry=(quote['ask'] if side>0 else quote['bid'])*(1+side*.0003)
        distance=abs(item['price']-item['stop']);fee=.001 if quote['market']=='spot' else .0006
        qty=1/(distance+entry*(fee+.0003)*2)
        chosen={}
        for policy,pick,version in [('champion',active,current_version),('challenger',challenger,pending_version)]:
            already_open=any(t['key']==key and not t.get('closed_at') and t.get(policy+'_accepted') for t in records)
            chosen[policy+'_accepted']=bool(pick and pick['method']==item['method'] and not already_open)
            chosen[policy+'_version']=version
        records.append(dict(id=identity,key=key,method=item['method'],features=item['features'],symbol=quote['symbol'],venue=quote['venue'],market=quote['market'],
            side=side,entry=entry,quantity=qty,stop=entry-side*distance,target=entry+side*2*distance,fee_rate=fee,
            opened_at=now,expires=now+(16*900 if key.endswith('intraday') else 42*14400),funding=0,funding_ids=[],**chosen))
    closed=[t for t in records if t.get('closed_at')][-1500:]
    state['adaptive_trials']=closed+[t for t in records if not t.get('closed_at')]


def tick_trials(state,now=None):
    now=now or time.time()
    quotes={(q['venue'],q['symbol'],q['market']):q for q in state['markets']}
    for trial in state.get('adaptive_trials',[]):
        q=quotes.get((trial['venue'],trial['symbol'],trial['market']))
        if not q:continue
        # Settlement records may arrive after the trade closed; amend the label.
        for event in q.get('settlements',[]):
            if trial['opened_at']<=event['time']<=trial.get('closed_at',now) and event['time'] not in trial['funding_ids']:
                amount=-trial['side']*trial['quantity']*(event.get('mark') or q['price'])*event['rate']
                trial['funding']+=amount;trial['funding_ids'].append(event['time'])
                if trial.get('closed_at'):trial['r']+=amount
        if trial.get('closed_at'):
            trial['funding_complete']=trial['market']=='spot' or q.get('funding_checked',0)>=trial['closed_at']
            continue
        if not all(q.get(k,0)>0 for k in ('price','bid','ask')) or now-q['observed']>15:continue
        if any(now-q.get(k+'_observed',q['observed'])>15 for k in ('bid','ask')):continue
        side=trial['side'];price=q['price']
        if side*(price-trial['stop'])<=0 or side*(price-trial['target'])>=0 or now>=trial['expires']:
            exit_price=(q['bid'] if side>0 else q['ask'])*(1-side*.0003)
            net=(exit_price-trial['entry'])*trial['quantity']*side-(trial['entry']+exit_price)*trial['quantity']*trial['fee_rate']+trial['funding']
            trial.update(closed_at=now,exit=exit_price,r=net,funding_complete=trial['market']=='spot')


def consider_promotion(controller,trials,key,now=None):
    now=now or time.time()
    pending=controller.get('pending')
    if not pending:return None
    window=[t for t in trials if t['key']==key and t.get('funding_complete',t.get('market')=='spot') and t.get('closed_at',now)+180<now and t['opened_at']>=max(pending['trained_at'],controller['pending_since'])
            and t['challenger_version']==pending['version']]
    current=stats([t for t in window if t['champion_accepted']])
    candidate=stats([t for t in window if t['challenger_accepted']])
    controller['forward']=dict(champion=current,challenger=candidate,minimum=20)
    if min(current['count'],candidate['count'])<20:return None
    passed=candidate['net_r']>max(0,current['net_r']+.1) and candidate['mean_r']>current['mean_r'] and candidate['drawdown_r']<=max(.1,current['drawdown_r'])
    if passed:
        previous=controller.get('champion')
        if previous:controller['previous']=previous
        controller.update(champion=pending,status='active',activated_at=now,promotions=controller['promotions']+1,
                          message='Model adayı, eğitiminden sonraki gerçek fiyat akışında kabul ölçütlerini geçti; devreye alındı.')
    else:controller['message']='Aday, ileri dönem net sonuç/düşüş karşılaştırmasını geçemedi; mevcut karar modeli korundu.'
    controller['history']=(controller.get('history',[])+[dict(version=pending['version'],time=now,promoted=passed,champion=current,challenger=candidate)])[-20:]
    controller.pop('pending',None)
    if controller.get('queue'):
        controller['pending']=controller['queue'].pop(0)
        controller['pending_since']=now
    return dict(promoted=passed,version=pending['version'])


def consider_rollback(controller,feedback,now=None):
    now=now or time.time()
    champion=controller.get('champion')
    if not champion:return None
    actual=[r for r in feedback if r.get('model_version')==champion['version'] and
            r['closed_at']>=controller.get('activated_at',0)][-20:]
    if len(actual)<20 or sum(r['r'] for r in actual)>-3:return None
    previous=controller.pop('previous',None)
    if previous:controller['champion']=previous
    else:controller.pop('champion',None)
    controller.update(status='active' if previous else 'statistical',activated_at=now,
                      message='Son 20 gerçek sanal kapanışta -3R sınırı aşıldı; model geri alındı, riskli yöntemler kısıtlandı.')
    controller['history']=(controller.get('history',[])+[dict(version=champion['version'],time=now,rollback=True)])[-20:]
    return dict(rollback=True,version=champion['version'])


def public_state(controller,choices,feedback,now=None):
    model=controller.get('champion') or controller.get('latest') or {}
    selected=decision(controller,choices,feedback,now)
    return dict(schema=SCHEMA,status=controller.get('status','training'),message=controller.get('message','Gerçek geçmişten yöntemler öğreniliyor.'),
        samples=model.get('samples',0),evaluation_samples=model.get('evaluation_samples',0),version=model.get('version',''),
        score=selected.get('model_score') if selected else None,selected_method=selected.get('method') if selected else None,
        qualification=model.get('qualification'),baseline=model.get('baseline'),feedback_count=len(feedback),
        families=[family_state(model,m,feedback,now or time.time()) for m in METHODS],
        forward=controller.get('forward'),promotions=controller.get('promotions',0),
        pending_version=controller.get('pending',{}).get('version'),queued_candidates=len(controller.get('queue',[])),candle_time=model.get('candle_time'),
        note='Öğrenme sanal giriş seçimini ve risk azaltmayı etkiler; toplam risk tavanı değişmez. Referans karşılaştırması 1R birimindedir ve birleşik portföy sonucu değildir.')
