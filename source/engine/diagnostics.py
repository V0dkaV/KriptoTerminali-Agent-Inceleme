"""Execution telemetry, independent of model-generated narrative."""
from collections import Counter
import time

from engine.adaptive import family_state, predict, METHODS, SCORE_THRESHOLD

LABELS=dict(waiting_rule='Giriş koşulu oluşmadı',volatile='Oynaklık filtresi bekletiyor',
            data_gap='Son mumlarda veri boşluğu var',
            warmup='Gösterge geçmişi yetersiz',preparing_model='Geçmiş değerlendirmesi hazırlanıyor',
            selector='Yöntemin maliyetli sonucu uygun değil',risk='Risk veya veri kontrolü engelledi',
            opened='Sanal giriş yapıldı',queued='Onaylı sinyal giriş kontrolünde',unavailable='Piyasa verisi alınamadı')


def selection_checks(controller,choices,feedback):
    model=controller.get('champion') or controller.get('latest') or {}
    now=time.time();checks=[]
    for item in choices:
        f=family_state(model,item['method'],feedback,now)
        score=predict(model,item['features'])
        reason='Uygun yöntem adayı.'
        code='eligible'
        if not model:code='preparing_model';reason='Bu bağlamın geçmiş değerlendirmesi henüz tamamlanmadı.'
        elif item['method'] not in model.get('policy',{}).get('methods',METHODS):code='policy';reason='Yöntem seçili model politikasının dışında.'
        elif not f['eligible']:code='samples';reason='Yöntem için yeterli kapanmış örnek yok.'
        elif f['paused']:code='loss_pause';reason='Son sanal sonuçlar nedeniyle yöntem geçici duraklatıldı.'
        elif controller.get('champion') and score is not None and score<model.get('policy',{}).get('minimum_score',SCORE_THRESHOLD):code='model_score';reason='Model skoru önceden tanımlı giriş eşiğinin altında.'
        elif not controller.get('champion') and f['expected_r']<=0:code='expected_result';reason='Maliyet sonrası öğrenilen ortalama pozitif değil.'
        checks.append(dict(method=item['method'],name=METHODS[item['method']],code=code,reason=reason,
                           history_count=f['history_count'],feedback_count=f['feedback_count'],expected_r=f['expected_r'],score=score))
    return checks


def snapshot(engine):
    now=time.time();state=engine.state
    rows=[r for r in state.get('decisions',{}).values() if r['symbol'] in engine.settings.allowlist and engine.enabled.get(r['strategy'])]
    counts=Counter()
    for r in rows:
        code=r.get('block_code')
        if not code:
            code='volatile' if r.get('regime')=='volatile' else 'warmup' if r.get('regime')=='unavailable' else 'selector' if r.get('candidates') else 'waiting_rule'
        counts[code]+=1
    stamps=[r.get('observed',0) for r in rows]
    symbols=engine.settings.allowlist if engine.mode!='DEMO' else [s for s in engine.settings.allowlist if s in ('BTCUSDT','ETHUSDT')]
    gate=dict(code='ready',blocked=False,label='Sinyal bekleniyor',message='Analiz sürüyor; uygun sinyal ve merkezi risk onayıyla yeni giriş yapılabilir.')
    mission=state.get('mission')
    if engine.closing:gate=dict(code='closing',blocked=True,label='Motor kapanıyor',message='Yeni girişler kapalı.')
    elif state.get('halt'):gate=dict(code='halted',blocked=True,label='Risk durdurması',message=state['halt'])
    elif not state.get('running'):gate=dict(code='paused',blocked=True,label='Yeni girişler duraklatıldı',message='Motoru başlatmak analizleri sürdürür; duraklatılmış görev ayrıca onay ister.')
    elif mission and mission.get('status')!='active':gate=dict(code='mission_paused',blocked=True,label='Görev onayı bekleniyor',message=(mission.get('reason') or 'Bütçeli görev duraklatıldı.')+' İşlem merkezi → Görev planını gör → Bu görevi onayla. Motorun çalışması görev onayının yerine geçmez.')
    elif mission and (mission.get('expires_at',0)<=now or mission.get('session_id')!=state.get('session_id')):gate=dict(code='mission_expired',blocked=True,label='Yeni görev onayı gerekli',message='Görev süresi veya hesap oturumu değişti; İşlem merkezinden yeni planı inceleyip onaylayın.')
    elif not any(engine.enabled.values()):gate=dict(code='strategies_off',blocked=True,label='Stratejiler kapalı',message='Analiz için en az bir otomatik strateji etkin olmalı.')
    return dict(entry_gate=gate,signal_intervals=['15m','4h'],heartbeat_age=max(0,now-engine.last_heartbeat) if engine.last_heartbeat else None,
                training=engine.training.snapshot(),analysis=dict(completed=len(rows),expected=engine.universe.snapshot(engine)['expected'],
                latest_at=max(stamps,default=0),oldest_at=min(stamps,default=0)),
                reasons=[dict(code=k,label=LABELS.get(k,k),count=v) for k,v in counts.most_common()],
                approved=counts['queued']+counts['opened'],positions=len(state['positions']),capital=state['initial'],
                last_dispatch_at=state.get('last_dispatch_at'),
                model_note='Fiyat/pozisyon takibi, kapanmış mum sinyali ve arka plan eğitimi ayrı çalışır. Yerel dil modeli giriş emri üretmez.')
