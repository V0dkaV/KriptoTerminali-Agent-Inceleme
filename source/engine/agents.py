"""Coordinator for local news interpretation and bounded strategy experiments."""
import asyncio
import copy
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from multiprocessing import get_context
import time

from engine.adaptive import METHODS,SCHEMA,train_candidate
from engine.training import reset_broken_pool
from engine.news import article_excerpt
from engine.local_ai import active_news_risk
from engine.knowledge import research_context,history_context


def quarantine_experimental_latest(controllers):
    """Repair old experiment results that bypassed the prospective gate."""
    changed = 0
    for controller in controllers.values():
        latest = controller.get('latest', {})
        champion = controller.get('champion', {})
        if latest.get('policy') and latest.get('version') != champion.get('version'):
            controller.pop('latest', None)
            if controller.get('pending'):
                controller['pending_since'] = time.time()
            controller.pop('forward', None)
            changed += 1
    return changed


def queue_experiment(old, candidate, now=None):
    """Keep an experiment separate from the baseline used by live selection."""
    state = copy.deepcopy(old)
    if not candidate.get('coefficients'):
        return state
    if state.get('schema') != SCHEMA:
        state = dict(schema=SCHEMA, history=[], promotions=0)
    version = candidate['version']
    known = [state.get('champion', {}), state.get('pending', {})] + state.get('queue', [])
    if any(item.get('version') == version for item in known):
        return state
    if not state.get('pending'):
        state['pending'] = copy.deepcopy(candidate)
        state['pending_since'] = time.time() if now is None else now
    else:
        state['queue'] = (state.get('queue', []) + [copy.deepcopy(candidate)])[-3:]
    return state


async def run_cycle(engine,*,allow_paused=False):
    if engine.ai_cycle_lock.locked():return
    async with engine.ai_cycle_lock:
        if not engine.settings.local_ai_enabled or engine.local_ai.disabled:return
        session_id = getattr(engine, 'state', {}).get('session_id')
        mode = getattr(engine, 'mode', 'PAPER')
        initially_running=getattr(engine,'state',{}).get('running',True)
        def active():
            return (not getattr(engine, 'closing', False) and mode == 'PAPER'
                    and getattr(engine, 'mode', 'PAPER') == mode
                    and getattr(engine, 'state', {}).get('session_id') == session_id
                    and (initially_running or allow_paused)
                    and getattr(engine,'state',{}).get('running',True)==initially_running
                    and engine.settings.local_ai_enabled and not engine.local_ai.disabled)
        if not active():return
        events=sorted([e for e in engine.news if not e.get('demo')],key=lambda e:e.get('published_at',''),reverse=True)[:4]
        articles=await asyncio.gather(*(asyncio.to_thread(article_excerpt,e) for e in events[:2]))
        context=[]
        for i,event in enumerate(events):
            context.append(dict(id=event['id'],title=event['title'][:160],source=event['source'],
                                published_at=event['published_at'],verification=event['verification'],
                                excerpt=(articles[i][:650] if i<len(articles) else event.get('description','')[:160])))
        async with engine.lock:
            summaries=[dict(key=key,model=c.get('latest',{}).get('version'),
                            net_r=c.get('latest',{}).get('qualification',{}).get('net_r'),
                            samples=c.get('latest',{}).get('samples')) for key,c in list(engine.controllers.items())[-4:]]
            experiments=engine.store.get('local_ai_experiments',[])
            past=[dict(hypothesis=e['proposal']['hypothesis'][:180],result=e.get('qualification'),status=e['status']) for e in experiments[-2:]]
        knowledge=research_context()
        history=history_context(getattr(engine,'history_service',None))
        ai_symbols=list(dict.fromkeys([p['symbol'] for p in getattr(engine,'state',{}).get('positions',[])]+getattr(getattr(engine,'universe',None),'last_batch',[])+engine.settings.allowlist))[:32]
        payload=dict(now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),events=context,methods=list(METHODS),allowed_symbols=ai_symbols,
                     knowledge=knowledge,requested_history=history,
                     evaluations=summaries,previous_experiments=past,
                     instruction='Kayıp üreten yöntemleri eleştirel değerlendir; tek bir sınırlı yöntem bileşimi deneyi seç. Haber etkisi yalnız belirsiz bir çıkarımdır.')
        answer=await asyncio.to_thread(engine.local_ai.infer,payload)
        if not active():return
        proposal=answer['experiment']
        report=dict(**answer,created_at=time.time(),model='Qwen3 4B / yerel',source_ids=[e['id'] for e in events],
                    knowledge=dict(version=knowledge['version'],card_ids=[c['id'] for c in knowledge['cards']],
                                   source_ids=sorted({s for c in knowledge['cards'] for s in c['sources']})),history_context=history)
        for item in report['events']:
            single={**report,'events':[item]}
            risks=[active_news_risk(single,symbol,engine.news)[0] for symbol in engine.settings.allowlist]
            item['applied_risk']='pause' if 'pause' in risks else 'reduce' if 'reduce' in risks else 'observe'
        async with engine.lock:
            if not active():return
            engine.ai_report=report
            engine.store.set('local_ai_report',report)
            engine.audit('local_ai','Yerel AI haber analizi tamamlandı; kaynaklarla bağlı yorum kaydedildi.')
        # At most one automatic experiment per six hours. AI produces no Python,
        # order APIs, or risk settings; a strict schema bounds its policy space.
        if not active() or not engine.settings.local_ai_research or (experiments and time.time()-experiments[-1]['created_at']<21600):return
        if proposal['symbol'] not in engine.settings.allowlist:return
        experiment=dict(id=str(time.time_ns()),created_at=time.time(),proposal=proposal,status='running')
        async with engine.lock:
            if not active() or not engine.settings.local_ai_research:return
            experiments=(engine.store.get('local_ai_experiments',[])+[experiment])[-30:]
            engine.store.set('local_ai_experiments',experiments)
        key=f"{proposal['venue']}:{proposal['symbol']}:{proposal['market']}:{proposal['strategy']}"
        pool = None
        try:
            rows=await asyncio.to_thread(engine.candles,proposal['symbol'],'15m' if proposal['strategy']=='intraday' else '4h',
                                         proposal['venue'],proposal['market'],True,'PAPER')
            if not active() or not engine.settings.local_ai_research or proposal['symbol'] not in engine.settings.allowlist:
                experiment.update(status='cancelled',message='Çalışma oturumu veya araştırma izni değişti; deney uygulanmadı.')
                return
            if engine.learning_pool is None:engine.learning_pool=ProcessPoolExecutor(max_workers=1,mp_context=get_context('spawn'))
            pool = engine.learning_pool
            candidate=await asyncio.get_running_loop().run_in_executor(pool,train_candidate,rows,
                proposal['strategy'],proposal['market'],engine.feedback(key),proposal)
            async with engine.lock:
                if not active() or not engine.settings.local_ai_research or proposal['symbol'] not in engine.settings.allowlist:
                    experiment.update(status='cancelled',message='Çalışma oturumu veya araştırma izni değişti; deney uygulanmadı.')
                else:
                    controllers={**engine.controllers,key:queue_experiment(engine.controllers.get(key,{}),candidate)}
                    engine.store.set('adaptive_controllers',controllers)
                    engine.controllers=controllers
                if experiment['status']=='cancelled':return
                experiment.update(status='forward_queue' if candidate.get('coefficients') else 'insufficient_data',
                                  version=candidate['version'],qualification=candidate['qualification'],baseline=candidate['baseline'],
                                  samples=candidate['samples'],evaluation_samples=candidate['evaluation_samples'])
                engine.audit('experiment','Yerel AI deneyinin maliyetli tarihsel karşılaştırması tamamlandı.',experiment)
        except asyncio.CancelledError:raise
        except Exception as exc:
            if isinstance(exc, BrokenProcessPool):reset_broken_pool(engine,pool)
            experiment.update(status='error',message='Deney verisi veya model hazırlanamadı; işlem kararına uygulanmadı.')
        finally:
            async with engine.lock:
                records=engine.store.get('local_ai_experiments',[])
                engine.store.set('local_ai_experiments',[experiment if e['id']==experiment['id'] else e for e in records])
