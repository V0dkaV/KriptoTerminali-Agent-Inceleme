"""Deterministic paper mandate, ranked signals and a durable decision journal.

The language model has no access to this executor. Caller holds Engine.lock.
"""
from __future__ import annotations

import copy
import hashlib
import math
import time
import uuid

from engine.models import Signal
from engine.exits import executable_price, remaining_net


class Operations:
    def __init__(self, engine):
        self.engine = engine
        # Restart never silently resumes an earlier authorization window.
        for state in engine.states.values():
            mission = state.get('mission')
            if mission and mission['status'] == 'active':
                mission.update(status='paused', reason='Uygulama yeniden açıldı; yeni görev onayı gerekiyor.')

    def validate(self, payload):
        e = self.engine
        if e.closing:return 'Motor kapanıyor; görev başlatılamaz.'
        if e.mode != 'PAPER':
            return 'İşlem görevi yalnız gerçek verili Sanal modda kullanılabilir.'
        if e.state['halt']:
            return e.state['halt']
        if not any(e.enabled.values()):
            return 'En az bir otomatik strateji açık olmalı.'
        capital = payload.get('capital')
        if isinstance(capital, bool) or not isinstance(capital, (float, int)) or not math.isfinite(capital) or capital < 10:
            return 'Görev bütçesi en az 10 USDT olmalı.'
        # No virtual money is created by a mission.
        available = sum(e.available(v, m) for v in ('Binance', 'Bybit') for m in ('spot', 'futures'))
        if capital > min(e.equity(), available) + 1e-7:
            return 'Görev bütçesi mevcut serbest sanal sermayeyi aşıyor.'
        for key, maximum in [('leverage', e.settings.leverage), ('max_positions', e.settings.max_positions), ('duration_hours', 72)]:
            if type(payload.get(key)) is not int or not 1 <= payload[key] <= maximum:
                return f'{key}: izin verilen aralık 1–{maximum}.'
        mission = e.state.get('mission')
        if mission and (mission['status'] == 'active' or any(p.get('mission_id') == mission['id'] for p in e.state['positions'])):
            return 'Önce mevcut görevi duraklat ve göreve ait açık pozisyonların kapanmasını bekle.'
        return ''

    def activate(self, payload):
        e = self.engine
        reason = self.validate(payload)
        if reason:
            return dict(ok=False, message=reason)
        now = time.time()
        e.state['mission'] = dict(id=uuid.uuid4().hex, status='active', **payload, created_at=now,
                                  expires_at=now + payload['duration_hours'] * 3600,
                                  session_id=e.state.get('session_id'), reason='',
                                  peak=payload['capital'], day=e.day(), day_equity=payload['capital'])
        e.state['running'] = True
        e.state['started_at'] = e.state['started_at'] or now
        e.audit('mission', 'Kullanıcı bütçeli sanal görevi onayladı.', e.state['mission'])
        self.mission_event('active','Bütçeli sanal görev kullanıcı onayıyla başladı.')
        e.save()
        e.scan_wake.set()
        return dict(ok=True, message='Sanal görev başladı. Yalnız risk kontrolünü geçen sinyaller kullanılacak; bütçenin tamamı harcanmak zorunda değil.', mission_id=e.state['mission']['id'])

    def pause(self):
        e = self.engine
        mission = e.state.get('mission')
        if not mission or mission['status'] != 'active':
            return dict(ok=False, message='Çalışan görev yok.')
        mission.update(status='paused', reason='Kullanıcı yeni görev girişlerini durdurdu.')
        e.audit('mission', mission['reason'], dict(id=mission['id']))
        self.mission_event('paused',mission['reason'])
        e.save()
        return dict(ok=True, message='Görev girişleri durdu. Açık pozisyonların koruyucu çıkışları sürüyor.')

    def mission_event(self,status,reason):
        e=self.engine
        rows=e.state.setdefault('operation_journal',[])
        rows.append(dict(id=uuid.uuid4().hex,time=time.time(),symbol='',venue='',market='',strategy='',
                         status=status,reason=reason,mission_id=e.state['mission']['id']))
        e.state['operation_journal']=rows[-500:]

    def accounting(self, mission):
        e = self.engine
        positions = [p for p in e.state['positions'] if p.get('mission_id') == mission['id']]
        closed = [p for p in e.state['closed'] if p.get('mission_id') == mission['id']]
        realized = sum(p['net'] for p in closed) + sum(p.get('partial_realized', 0) for p in positions)
        used = sum((p['entry'] * p['quantity'] if p['market'] == 'spot' else p['initial_margin']) + p['entry_fee'] for p in positions)
        # Funding received/paid on the remaining slice is already cash settled.
        remaining_funding = sum(p.get('funding', 0) for p in positions)
        available = max(0., min(mission['capital'], mission['capital'] + realized + remaining_funding) - used)
        unrealized=0.
        valuation_fresh=True
        for p in positions:
            q=e.quote(p['venue'],p['symbol'],p['market']) or {}
            valuation_fresh=valuation_fresh and all(q.get(k,0)>0 and time.time()-q.get(k+'_observed',0)<=15 for k in ('bid','ask'))
            price=executable_price(p,q) if q.get('bid',0)>0 and q.get('ask',0)>0 else p.get('price',p['entry'])
            unrealized+=remaining_net(p,price)
        return dict(used_capital=used, available_capital=available, open_risk=sum(p['planned_risk'] for p in positions),
                    net=realized + unrealized, realized=realized, positions=len(positions),valuation_fresh=valuation_fresh)

    def risk_limit(self, mission, key):
        return min(getattr(self.engine.settings,key), mission.get('approved_risk',{}).get(key,getattr(self.engine.settings,key)))

    def enforce(self):
        e = self.engine
        mission = e.state.get('mission')
        if not mission or mission['status'] != 'active':
            return
        a = self.accounting(mission)
        equity = mission['capital'] + a['net']
        mission['peak'] = max(mission.get('peak', mission['capital']), equity)
        if mission.get('day') != e.day():
            mission.update(day=e.day(), day_equity=equity)
        reason = ''
        if mission['session_id'] != e.state.get('session_id'):
            reason = 'Sanal hesap oturumu değişti.'
        elif time.time() >= mission['expires_at']:
            mission['status'] = 'expired'
            reason = 'Görevin yeni giriş süresi tamamlandı.'
        elif equity <= mission['day_equity'] * (1 - self.risk_limit(mission,'daily_loss') / 100):
            reason = 'Görev bütçesinin günlük kayıp eşiğine ulaşıldı.'
        elif equity <= mission['peak'] * (1 - self.risk_limit(mission,'drawdown') / 100):
            reason = 'Görev bütçesinin hesap düşüşü eşiğine ulaşıldı.'
        if reason:
            if mission['status'] == 'active': mission['status'] = 'paused'
            mission['reason'] = reason + ' Koruyucu çıkışlar devam ediyor.'
            e.audit('mission', mission['reason'], dict(id=mission['id']))
            self.mission_event(mission['status'],mission['reason'])
            e.save()

    def limits(self):
        self.enforce()
        e = self.engine
        mission = e.state.get('mission')
        if not mission:
            return {}, ''
        if mission['status'] != 'active':
            return {}, mission.get('reason') or 'Bütçeli görev yeni girişlere kapalı.'
        a = self.accounting(mission)
        if a['positions'] >= min(mission['max_positions'], e.settings.max_positions):
            return {}, 'Görevin eşzamanlı pozisyon sınırı.'
        if a['available_capital'] < 10:
            return {}, 'Görevde serbest minimum emir bütçesi kalmadı.'
        capital = min(mission['capital'], max(0., mission['capital'] + a['net']))
        risk = min(capital * self.risk_limit(mission,'trade_risk') / 100, capital * self.risk_limit(mission,'total_risk') / 100 - a['open_risk'])
        if risk <= 1e-8:
            return {}, 'Görevin toplam açık risk bütçesi doldu.'
        return dict(budget_limit=a['available_capital'], requested_leverage=min(mission['leverage'],e.settings.leverage),
                    absolute_risk_cap=risk, mission_id=mission['id']), ''

    @staticmethod
    def identity(signal):
        return f'{signal.venue}:{signal.symbol}:{signal.market}:{signal.strategy}:{signal.candle_time}'

    def receipt_id(self, identity, mode=None, session_id=None):
        return hashlib.sha256(f'{mode or self.engine.mode}:{session_id or self.engine.state.get("session_id")}:{identity}'.encode()).hexdigest()

    def publish(self, signal):
        e = self.engine
        identity = self.identity(signal)
        q = e.quote(signal.venue, signal.symbol, signal.market) or {}
        spread = (q.get('ask', 0) - q.get('bid', 0)) / max(q.get('price', 0), 1e-9) * 100
        # Transparent comparison heuristic, never a win probability. Only ML-
        # approved strategy signals enter this list; liquidity/spread break ties.
        score = round(max(0., min(100., (signal.model_score or 0) * 70 + signal.risk_multiplier * 20 + max(0, 10 - spread * 100))), 2)
        item = dict(id=identity, signal=signal.model_dump(), venue=signal.venue, symbol=signal.symbol,
                    market=signal.market, strategy=signal.strategy, side=signal.side, method=signal.method,
                    score=score, score_label='Karşılaştırma puanı; kazanma olasılığı değildir', observed=time.time(),
                    candle_time=signal.candle_time, expires_at=signal.candle_time + (1800 if signal.strategy == 'intraday' else 28800),
                    status='eligible', reason='Onaylı strateji sinyali; merkezi risk kontrolü bekleniyor.')
        candidates = e.state.setdefault('operation_candidates', {})
        prior = candidates.get(identity)
        if prior and (prior['status']=='opened' or (prior['status']=='blocked' and identity in e.state['last_signals'])): return
        candidates[identity] = item
        if len(candidates) > 384:
            e.state['operation_candidates'] = dict(sorted(candidates.items(), key=lambda kv: kv[1]['observed'])[-384:])

    def journal(self, item, status, reason, position_id=None):
        e = self.engine
        # At most one final automatic decision for a signal, across restarts.
        key = hashlib.sha256(item['id'].encode()).hexdigest()
        rows = e.state.setdefault('operation_journal', [])
        if any(row['id'] == key for row in rows): return
        rows.append(dict(id=key, time=time.time(), symbol=item['symbol'], venue=item['venue'], market=item['market'],
                         strategy=item['strategy'], status=status, reason=reason, score=item['score'],
                         mission_id=(e.state.get('mission') or {}).get('id'), position_id=position_id,
                         candle_time=item['candle_time'], method=item['method'], model_version=item['signal']['model_version']))
        e.state['operation_journal'] = rows[-500:]

    def dispatch(self):
        e = self.engine
        self.enforce()
        ready=e.refresh_entry_candidates()
        dirty=False
        candidates = sorted(e.state.get('operation_candidates', {}).values(), key=lambda x: (-x['score'], x['id']))
        for item in candidates:
            if item['status'] != 'eligible': continue
            identity = item['id']
            if time.time() >= item['expires_at']:
                item.update(status='stale', reason='Sinyalin giriş penceresi geçti.')
                self.journal(item, 'stale', item['reason'])
                dirty=True
                continue
            if not e.state['running']: break
            receipt_id=self.receipt_id(identity)
            if identity in e.state['last_signals'] or e.store.signal_processed(receipt_id):
                item.update(status='blocked', reason='Bu mumun sinyali daha önce işlendi.')
                dirty=True
                continue
            if ready is not None and ':'.join(identity.split(':')[:4]) not in ready:
                item['reason']='Güncel strateji analizi bekleniyor; eğitim sonucu emir değildir.'
                continue
            limits, reason = self.limits()
            if reason:
                # Mission paused/expired is temporary: retain fresh proposals,
                # but never allow a legacy resume to bypass the mandate.
                item['reason'] = reason
                continue
            before = copy.deepcopy(e.state)
            try:
                with e.store.atomic():
                    if not e.store.claim_signal(receipt_id,e.mode,e.state.get('session_id'),identity):
                        item.update(status='blocked',reason='Bu mumun sinyali daha önce işlendi.')
                        e.save()
                        continue
                    outcome = e.open_signal(Signal(**item['signal']), **limits)
                    e.state['last_signals'] = (e.state['last_signals'] + [identity])[-500:]
                    item.update(status='opened' if outcome['ok'] else 'blocked', reason=outcome['message'])
                    self.journal(item, item['status'], item['reason'], outcome.get('id'))
                    decision = e.state.get('decisions', {}).get(':'.join(identity.split(':')[:4]))
                    if decision: decision.update(message=outcome['message'], accepted=outcome['ok'],block_code='opened' if outcome['ok'] else 'risk')
                    e.save()
            except Exception:
                e.states[e.mode] = before
                raise
        e.state["last_dispatch_at"]=time.time()
        if dirty:e.save()

    def snapshot(self):
        e = self.engine
        self.enforce()
        limits, gate = self.limits()
        opportunities = []
        for item in sorted(e.state.get('operation_candidates', {}).values(), key=lambda x: (-x['score'], x['id']))[:60]:
            row = {k: v for k, v in item.items() if k != 'signal'}
            if row['status'] == 'eligible':
                if time.time() >= item['expires_at']: row.update(status='stale', reason='Sinyalin giriş penceresi geçti.')
                elif gate: row.update(status='blocked', reason=gate)
                else:
                    preview = e.open_signal(Signal(**item['signal']), preview=True, **limits)
                    if preview['ok']: row.update({k: preview[k] for k in ('entry', 'stop', 'target', 'planned_risk', 'capital_required', 'leverage')})
                    else: row.update(status='blocked', reason=preview['message'])
            opportunities.append(row)
        decisions = [d for d in e.state.get('decisions', {}).values() if d['symbol'] in e.settings.allowlist and e.enabled.get(d['strategy'])]
        mission = copy.deepcopy(e.state.get('mission'))
        if mission:
            mission.update(self.accounting(mission))
            mission['effective_leverage']=min(mission['leverage'],e.settings.leverage)
            mission['effective_max_positions']=min(mission['max_positions'],e.settings.max_positions)
        return dict(mode=e.mode, session_id=e.state.get('session_id'), timestamp=time.time(), mission=mission,
                    coverage=dict(analyzed=len(decisions), total=len(e.settings.allowlist) * sum(bool(v) for v in e.enabled.values()) * 4,
                                  updated_at=max((d.get('observed', 0) for d in decisions), default=0)),
                    opportunities=opportunities, decisions=list(reversed(e.state.get('operation_journal', [])))[0:100])
