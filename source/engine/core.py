from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import time
import uuid
import copy
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from zoneinfo import ZoneInfo

from engine.market import Exchange, iso_now
from engine.models import CATALOG, GroupMachine, RiskSettings, Signal, position_size, net_pnl
from engine.news import collect_news, entry_restriction
from engine.research import demo_candles, analyze_candles
from engine.store import Store
from engine.stream import listen
from engine.margin import margin_status, isolated_adjustment
from engine.exits import executable_price, initialize as initialize_exits, remaining_net, adaptive_action, tighten_stop, quantity_at
from engine.portfolio import DEFAULT_SYMBOLS, PROFILES, concentration, returns, style
from engine.local_ai import LocalAI,active_news_risk
from engine.agents import run_cycle, quarantine_experimental_latest
from engine.state_transaction import state_transaction
from engine.knowledge import library_snapshot
from engine.operations import Operations
from engine.training import BackgroundTraining
from engine.diagnostics import snapshot as execution_snapshot, selection_checks
from engine.universe import Universe, PRODUCTS
from engine import scanner_cache
from engine.adaptive import (SCHEMA, METHODS, options, train_candidate, update_controller,
                             decision, register_trials, tick_trials, consider_promotion, consider_rollback, public_state)


class Engine:
    def __init__(self, data_dir):
        self.store = Store(data_dir)
        saved=self.store.get('settings', {})
        # Upgrade only the original two-coin default; keep custom universes and
        # lower user limits. Account state, balance and trade records are separate.
        if saved and not self.store.get('universe_v4'):
            if set(saved.get('allowlist',[]))=={'BTCUSDT','ETHUSDT'}:saved['allowlist']=DEFAULT_SYMBOLS.copy()
            if 'risk_profile' not in saved and all(saved.get(k,v)==v for k,v in dict(trade_risk=.5,total_risk=2.,daily_loss=2.,drawdown=10.,leverage=3,max_positions=4).items()):
                saved.update({k:v for k,v in PROFILES['mixed'].items() if k!='name'})
                saved['risk_profile']='mixed'
        if saved and 'auto_universe' not in saved:
            saved['auto_universe']=set(saved.get('allowlist',[]))==set(DEFAULT_SYMBOLS)
        self.settings = RiskSettings(**saved)
        self.store.set('settings',self.settings.model_dump())
        self.store.set('universe_v4',True)
        self.mode = self.store.get('mode', 'PAPER')
        if self.mode not in ('DEMO', 'PAPER'): self.mode = 'PAPER'
        self.credentials = {}
        self.connections = {v: dict(venue=v, status='disconnected', authenticated=False) for v in ('Binance', 'Bybit')}
        self.states = {}
        for mode in ('DEMO', 'PAPER'):
            self.states[mode] = self.store.get('state:' + mode) or self.new_state(mode)
            self.states[mode]['running'] = False
            fault=self.states[mode].pop('engine_fault',None)
            if fault and self.states[mode].get('halt')==fault:self.states[mode]['halt']=''
        self.enabled = self.store.get('enabled', {'intraday': True, 'swing': True})
        self.cache = {}
        self.jobs = []
        self.reports = self.store.reports()
        self.news = self.store.get('news', [])
        self.news_sources = self.store.get('news_sources', [])
        self.last_news = 0
        self.lock = asyncio.Lock()
        self.tasks = []
        self.tick = 0
        self.last_heartbeat=None
        self.closing = False
        self.universe = Universe(self.store.get('exchange_universe',{}))
        self.last_alert = set(self.store.get('sent_alerts', []))
        self.funding_cache = {}
        self.telegram = None
        self.ai_key = None
        self.scan_wake = asyncio.Event()
        self.stream_last_check = 0
        self.controllers=self.store.get('adaptive_controllers',{})
        quarantined=quarantine_experimental_latest(self.controllers)
        if quarantined:
            self.store.set('adaptive_controllers',self.controllers)
            self.audit('model',f'{quarantined} onaysız deney modeli aktif seçimden ayrıldı; geçmiş değerlendirmesi yenilenecek.')
        self.learning_pool=None
        self.history_bootstrapped=set()
        self.analysis_cache={}
        self.return_history={}
        self.controllers_dirty=False
        self.local_ai=LocalAI(data_dir)
        self.ai_cycle_lock=asyncio.Lock()
        self.ai_report=self.store.get('local_ai_report',{})
        self.operations=Operations(self)
        with self.store.atomic():
            for receipt_mode,state in self.states.items():
                for identity in state.get('last_signals',[]):
                    self.store.claim_signal(self.operations.receipt_id(identity,receipt_mode,state.get('session_id')),receipt_mode,state.get('session_id'),identity)
        self.training=BackgroundTraining(self,train_candidate)

    @property
    def state(self): return self.states[self.mode]

    def new_state(self, mode):
        balance = self.settings.paper_balance
        wallets = {f'{v}:{m}': balance/4 for v in ('Binance', 'Bybit') for m in ('spot', 'futures')}
        state = dict(running=False, wallets=wallets, initial=balance, positions=[], closed=[], groups=[],
                     peak=balance, day=self.day(), day_equity=balance, halt='', markets=[], equity_curve=[],
                     started_at=None, paper_days=[], last_signals=[], sample=(mode == 'DEMO'),
                     fees=0.0, funding=0.0, source_status='demo' if mode == 'DEMO' else 'waiting',
                     last_tick=0, accumulated_seconds=0, decisions={}, learning={}, session_id=uuid.uuid4().hex)
        if mode == 'DEMO':
            now = time.time()
            cumulative = balance
            for i, pnl in enumerate([42, -18, 65, 95, -36, 88, 51, -24, 76, 45]):
                fee = 1.8 + i*0.13
                net = pnl-fee
                wallet = 'Binance:futures' if i % 2 == 0 else 'Bybit:futures'
                wallets[wallet] += net
                cumulative += net
                state['fees'] += fee
                state['closed'].append(dict(id='sample-'+str(i), symbol='BTCUSDT' if i%2 == 0 else 'ETHUSDT',
                    venue='Binance' if i%2 == 0 else 'Bybit', market='futures', side='long' if i%3 else 'short',
                    strategy='intraday' if i%2 == 0 else 'swing', quantity=0.01, entry=75000 if i%2 == 0 else 2800,
                    exit=75100 if i%2 == 0 else 2820, net=net, gross=pnl, fees=fee, funding=0,
                    closed_at=now-(10-i)*7200, reason='Demo örnek kaydı', sample=True))
                state['equity_curve'].append(dict(time=int(now-(10-i)*7200), value=round(cumulative, 2)))
            for venue in ('Binance', 'Bybit'):
                for symbol in ('BTCUSDT', 'ETHUSDT'):
                    for market in ('spot', 'futures'):
                        price = 76984.6 if symbol == 'BTCUSDT' else 2894.72
                        price *= (1.00015 if venue == 'Bybit' else 1) * (1.0003 if market == 'futures' else 1)
                        state['markets'].append(dict(symbol=symbol, venue=venue, market=market, price=price,
                            bid=price*.99995, ask=price*1.00005, change=2.34 if symbol=='BTCUSDT' else -0.82,
                            volume=12_480_000_000 if symbol=='BTCUSDT' else 6_780_000_000, observed=now, funding=0.0001))
            state['source_status'] = 'demo'
            state['peak'] = cumulative
        return state

    def day(self): return datetime.now(ZoneInfo('Europe/Istanbul')).strftime('%Y-%m-%d')

    def save(self):
        self.store.set('state:' + self.mode, self.state)
        self.store.set('mode', self.mode)

    def quote(self, venue, symbol, market):
        return next((r for r in self.state['markets'] if r['venue']==venue and r['symbol']==symbol and r['market']==market), None)

    def available(self, venue, market):
        wallet = self.state['wallets'][f'{venue}:{market}']
        if market == 'futures':
            wallet -= sum(max(0,p.get('initial_margin',p['quantity']*p['entry']/p['leverage'])+p.get('funding',0))
                          for p in self.state['positions'] if p['venue']==venue and p['market']==market)
        return max(0, wallet)

    def equity(self):
        total = sum(self.state['wallets'].values())
        for p in self.state['positions']:
            price = p.get('price', p['entry'])
            if p['market'] == 'spot': total += p['quantity']*price
            else:
                gross=(price-p['entry'])*p['quantity']*(1 if p['side']=='long' else -1)
                collateral=p.get('initial_margin',p['quantity']*p['entry']/p['leverage'])+p.get('funding',0)
                # Quotes may mark through liquidation while the executable book
                # is stale. The isolated model never spends another position's cash.
                total+=max(gross,-collateral)
        return total

    def audit(self, kind, message, payload=None):
        self.store.audit(self.mode, kind, message, payload)

    def risk_gate(self, sig):
        if self.closing:return 'Motor kapanıyor; yeni girişler kapalı.'
        s = self.state
        if s['halt']: return s['halt']
        if not s['running']: return 'Yeni girişler durduruldu.'
        if not self.enabled.get(sig.strategy):return 'Strateji kapalı; yeni giriş reddedildi.'
        if self.mode not in ('DEMO', 'PAPER'): return 'Bu modda emir gönderimi etkin değil.'
        if sig.symbol not in self.settings.allowlist: return 'Coin izin listesinde değil.'
        if self.mode=='PAPER' and self.settings.auto_universe and self.universe.catalogs and not self.universe.supports(sig.venue,sig.symbol,sig.market,fresh=True):
            return 'Bu ürünün güncel borsa listesi doğrulanamadı; yeni giriş bekliyor.'
        if sig.side == 'short' and sig.market == 'spot': return 'Spot borçlanma / short desteklenmiyor.'
        if (sig.side=='long' and not sig.stop < sig.price < sig.target) or (sig.side=='short' and not sig.target < sig.price < sig.stop):
            return 'Stop veya hedef yönü geçersiz.'
        if not all(math.isfinite(v) for v in (sig.price, sig.stop, sig.target)): return 'Geçersiz fiyat.'
        if len(s['positions']) + sum(g['status'] not in ('closed','cancelled') for g in s['groups']) >= self.settings.max_positions:
            return 'Eşzamanlı pozisyon/grup sınırı.'
        if any(p['symbol']==sig.symbol and p['venue']==sig.venue and p['market']==sig.market for p in s['positions']):
            return 'Piyasa ve sembol başka bir açık pozisyona ait.'
        q = self.quote(sig.venue, sig.symbol, sig.market)
        if not q or not all(math.isfinite(q.get(k,0)) and q.get(k,0)>0 for k in ('price','bid','ask')) or q['bid']>q['ask'] or time.time()-q['observed'] > 30: return 'Fiyat verisi güncel veya geçerli değil.'
        if self.mode=='PAPER' and any(time.time()-q.get(field+'_observed',q['observed'])>15 for field in ('bid','ask')):
            return 'Emir defteri güncel değil; yeni giriş bekliyor.'
        if self.mode=='PAPER' and sig.market=='futures' and (not math.isfinite(q.get('mark_price',0)) or q.get('mark_price',0)<=0 or time.time()-q.get('mark_price_observed',0)>15):
            return 'Vadeli işaret fiyatı güncel değil; yeni giriş bekliyor.'
        step=900 if sig.strategy=='intraday' else 14400
        if self.mode=='PAPER' and sig.candle_time+step>time.time():
            return 'Sinyal mumu henüz kapanmadı; yeni giriş bekliyor.'
        if self.mode=='PAPER' and time.time()-(sig.candle_time+step)>step+60:
            return 'Sinyal mumu güncel değil.'
        if q['ask']/q['bid']-1 > 0.002: return 'Spread %0,2 sınırının üzerinde.'
        if self.mode == 'PAPER':
            if q.get('volume',0)<5_000_000:return '24 saatlik USDT hacmi 5 milyonun altında; likidite filtresi.'
            if self.settings.local_ai_enabled and self.settings.local_ai_news_controls:
                ai_risk,ai_reason=active_news_risk(self.ai_report,self.universe.canonical(sig.symbol),self.news)
                if ai_risk=='pause':return 'Yerel AI haber risk penceresi (en fazla 15dk): '+ai_reason
            restriction = entry_restriction(self.news, self.universe.canonical(sig.symbol))
            if restriction: return restriction
            healthy = [r for r in self.news_sources if r['status']=='ok' and time.time()-r['observed']<1800]
            if not healthy: return 'Haber/takvim katmanı güncel değil; yeni giriş bekliyor.'
        context=self.state.get('regimes',{}).get(f'{sig.venue}:{sig.symbol}:{sig.market}:{sig.strategy}')
        if context and context['regime'] in ('volatile','unavailable'):
            return 'Rejim kontrolü yeni girişi bekletiyor: '+context['regime']
        return None

    def open_signal(self, sig, *, budget_limit=None, requested_leverage=None, origin='strategy', preview=False, absolute_risk_cap=None, mission_id=None):
        before = copy.deepcopy(self.state)
        try:
            with self.store.atomic():
                return self._open_signal(sig,budget_limit=budget_limit,requested_leverage=requested_leverage,origin=origin,preview=preview,absolute_risk_cap=absolute_risk_cap,mission_id=mission_id)
        except Exception:
            self.states[self.mode] = before
            raise

    def _open_signal(self, sig, *, budget_limit=None, requested_leverage=None, origin='strategy', preview=False, absolute_risk_cap=None, mission_id=None):
        if origin not in ('strategy','chat') or (origin=='chat' and self.mode!='PAPER'):
            return dict(ok=False,message='Sohbet işlemi yalnız gerçek verili sanal hesapta kullanılabilir.')
        if budget_limit is not None and (not isinstance(budget_limit,(float,int)) or not math.isfinite(budget_limit) or budget_limit<10):
            return dict(ok=False,message='İşlem bütçesi en az 10 USDT olmalı.')
        if requested_leverage is not None and (type(requested_leverage) is not int or not 1<=requested_leverage<=self.settings.leverage):
            return dict(ok=False,message=f'Seçili profil en fazla {self.settings.leverage}x kaldıraca izin veriyor; profil sohbetten değiştirilmez.')
        if absolute_risk_cap is not None and (type(absolute_risk_cap) not in (int,float) or not math.isfinite(absolute_risk_cap) or absolute_risk_cap<=0):
            return dict(ok=False,message='Görev risk bütçesi pozitif ve sonlu olmalı.')
        reason = self.risk_gate(sig)
        equity = self.equity()
        q = self.quote(sig.venue, sig.symbol, sig.market)
        fee_rate = 0.001 if sig.market == 'spot' else 0.0006
        if reason:
            if not preview:self.audit('rejected', reason, sig.model_dump())
            return dict(ok=False, message=reason)
        # Fill at executable bid/ask plus hypothetical paper slippage, not last trade.
        side = 1 if sig.side=='long' else -1
        entry = (q['ask'] if side==1 else q['bid']) * (1+side*0.0003)
        distance = abs(sig.price-sig.stop)
        stop, target = entry-side*distance, entry+side*2*distance
        if not all(math.isfinite(v) and v>0 for v in (entry,stop,target)):
            reason='Güncel gerçekleşme fiyatında stop/hedef geçersiz; yeni analiz bekleniyor.'
            if not preview:self.audit('rejected',reason,sig.model_dump())
            return dict(ok=False,message=reason)
        leverage = (requested_leverage or self.settings.leverage) if sig.market=='futures' else 1
        strategy_share=next((a['share'] for a in self.allocation() if a['strategy']==sig.strategy),0)
        strategy_used=sum(p['planned_risk'] for p in self.state['positions'] if p['strategy']==sig.strategy)
        portfolio_used=sum(p['planned_risk'] for p in self.state['positions'])
        key=f'{sig.venue}:{sig.symbol}:{sig.market}:{sig.strategy}'
        risk_style,style_factor=style(self.settings,sig,self.feedback(key))
        concentration_rate,concentration_info=concentration(self.settings,sig,self.state['positions'],equity,self.return_history,self.universe.aliases())
        risk_factor=style_factor*sig.risk_multiplier
        rate=max(0,min(self.settings.trade_risk*risk_factor,
                       concentration_rate,
                       self.settings.total_risk*strategy_share/100-strategy_used/max(equity,1)*100,
                       self.settings.total_risk-portfolio_used/max(equity,1)*100))
        if self.mode=='PAPER' and self.settings.local_ai_enabled and self.settings.local_ai_news_controls:
            if active_news_risk(self.ai_report,self.universe.canonical(sig.symbol),self.news)[0]=='reduce':
                rate*=.5
                risk_factor*=.5
        available=self.available(sig.venue,sig.market)
        if budget_limit is not None:available=min(available,budget_limit)
        if absolute_risk_cap is not None:rate=min(rate,absolute_risk_cap/max(equity,1)*100*risk_factor)
        qty, risk = position_size(equity, entry, stop, rate, fee_rate+0.0003,available,leverage)
        existing = sum(p['planned_risk'] for p in self.state['positions'])
        existing += sum(g.get('planned_risk',0) for g in self.state['groups'] if g['status'] not in ('closed','cancelled'))
        if existing+risk > equity*self.settings.total_risk/100+1e-7:
            reason = 'Birleşik portföy açık risk sınırı.'
        elif qty*entry < 10: reason = 'Risk bütçesiyle minimum sanal emir büyüklüğüne ulaşılamıyor.'
        elif sum(p['planned_risk'] for p in self.state['positions'] if p['strategy']==sig.strategy)+risk > equity*self.settings.total_risk/100*next((a['share']/100 for a in self.allocation() if a['strategy']==sig.strategy),0)+1e-7:
            reason = 'Stratejinin sınırlı dinamik risk bütçesi yetersiz.'
        if reason:
            if not preview:self.audit('rejected',reason,sig.model_dump())
            return dict(ok=False,message=reason)
        if preview:
            return dict(ok=True,entry=entry,stop=stop,target=target,quantity=qty,planned_risk=risk,
                        notional=entry*qty,entry_fee=entry*qty*fee_rate,
                        capital_required=entry*qty/leverage+entry*qty*fee_rate,leverage=leverage)
        id = uuid.uuid4().hex
        fee = entry*qty*fee_rate
        position = dict(id=id,symbol=sig.symbol,venue=sig.venue,market=sig.market,side=sig.side,
                        strategy=sig.strategy,quantity=qty,entry=entry,price=q['price'],stop=stop,target=target,
                        planned_risk=risk,entry_fee=fee,funding=0,fee_rate=fee_rate,leverage=leverage,
                        opened_at=time.time(),candle_time=sig.candle_time,reason=sig.reason,
                        protection='simulated',sample=self.mode=='DEMO',cost_estimated=True,
                        initial_margin=entry*qty/leverage if sig.market=='futures' else 0,
                        maintenance_rate=0.01,session_id=self.state.get('session_id'),origin=origin,
                        mission_id=mission_id)
        position.update(method=sig.method,model_version=sig.model_version,model_score=sig.model_score,
                        risk_multiplier=sig.risk_multiplier,features=sig.features,risk_style=risk_style,
                        risk_profile=self.settings.risk_profile,concentration=concentration_info)
        initialize_exits(position, self.settings.exit_policy if self.mode=='PAPER' else 'fixed')
        self.state['wallets'][f'{sig.venue}:{sig.market}'] -= fee + (entry*qty if sig.market=='spot' else 0)
        self.state['fees'] += fee
        self.state['positions'].append(position)
        self.store.ledger(id+':entry',self.mode,'entry_fee',-fee,position)
        self.audit('entry', f"{sig.symbol} {sig.side.upper()} sanal pozisyon açıldı.",position)
        self.save()
        return dict(ok=True,message='Sanal pozisyon açıldı.',id=id)

    def close_position(self, id, reason='Kullanıcı kapattı'):
        return self._exit_transaction(id, reason, False)

    def partial_position(self, id):
        return self._exit_transaction(id, '1R kısmi kâr alımı', True)

    def _exit_transaction(self, id, reason, partial):
        before = copy.deepcopy(self.state)
        try:
            with self.store.atomic():
                return self._close_position(id, reason, partial=partial)
        except Exception:
            self.states[self.mode] = before
            raise

    def _close_position(self, id, reason='Kullanıcı kapattı', *, partial=False):
        p = next((p for p in self.state['positions'] if p['id']==id),None)
        if not p: return dict(ok=False,message='Pozisyon bulunamadı.')
        if partial and (p.get('exit_policy','fixed')!='adaptive' or p.get('partial_fills')):
            return dict(ok=False,message='Kısmi çıkış daha önce gerçekleşti veya bu pozisyonda etkin değil.')
        q = self.quote(p['venue'],p['symbol'],p['market'])
        if not q or not all(math.isfinite(q.get(k,0)) and q.get(k,0)>0 for k in ('price','bid','ask')) or q['bid']>q['ask'] or time.time()-q['observed']>30:
            return dict(ok=False,message='Kapanış için güncel fiyat bekleniyor; gerçekleşmiş sayılmadı.')
        if self.mode=='PAPER' and any(time.time()-q.get(k+'_observed',q['observed'])>15 for k in ('bid','ask')):
            return dict(ok=False,message='Kapanış için güncel alış/satış fiyatı bekleniyor; gerçekleşmiş sayılmadı.')
        price = executable_price(p,q)
        if partial and adaptive_action(p,price)!='partial':
            return dict(ok=False,message='Kısmi çıkış koşulu veya minimum büyüklük uygun değil.')
        fraction=.5 if partial else 1.
        quantity=p['quantity']*fraction
        entry_fee=p['entry_fee']*fraction
        funding=p.get('funding',0)*fraction
        initial_margin=p.get('initial_margin',p['entry']*p['quantity']/p['leverage'])*fraction
        side = 1 if p['side']=='long' else -1
        gross = (price-p['entry'])*quantity*side
        exit_fee = price*quantity*p['fee_rate']
        fees = entry_fee+exit_fee
        adjustment=0
        if p['market']=='futures':
            adjustment=isolated_adjustment(initial_margin,funding,gross,exit_fee,reason)
        net = net_pnl(gross,fees,funding)+adjustment
        at=time.time()
        fill=dict(quantity=quantity,price=price,gross=gross,entry_fee=entry_fee,exit_fee=exit_fee,
                  funding=funding,net=net,closed_at=at,reason=reason,initial_margin=initial_margin,settlement_adjustment=adjustment)
        receipt=id+(':partial:1r' if partial else ':exit')
        # Receipt and all balances/state changes share one SQLite transaction.
        # An unexpected pre-existing receipt blocks reapplication after recovery.
        if not self.store.ledger(receipt,self.mode,'partial_trade' if partial else 'closed_trade',net,dict(position_id=id,**fill)):
            return dict(ok=False,message='Bu çıkış kaydı daha önce işlendi; tekrar uygulanmadı.')
        wallet = f"{p['venue']}:{p['market']}"
        self.state['wallets'][wallet] += (price*quantity if p['market']=='spot' else gross)-exit_fee+adjustment
        self.state['fees'] += exit_fee
        if partial:
            p.setdefault('partial_fills',[]).append(fill)
            p['quantity']-=quantity
            p['entry_fee']-=entry_fee
            p['funding']-=funding
            p['initial_margin']=max(0,p.get('initial_margin',initial_margin*2)-initial_margin)
            p['planned_risk']*=1-fraction
            p['remaining_risk']=p['planned_risk']
            p['partial_realized']=sum(f['net'] for f in p['partial_fills'])
            tighten_stop(p,price)
            self.audit('partial_exit',f"{p['symbol']} yarısı kapandı · net {net:+.2f} USDT",fill)
            self.save()
            return dict(ok=True,message=f'Kısmi sanal kâr alındı: {net:+.2f} USDT',receipt=receipt)
        partials=p.get('partial_fills',[])
        total_quantity=p.get('original_quantity',p['quantity'])
        total_gross=gross+sum(f['gross'] for f in partials)
        total_fees=fees+sum(f['entry_fee']+f['exit_fee'] for f in partials)
        total_funding=funding+sum(f['funding'] for f in partials)
        total_adjustment=adjustment+sum(f.get('settlement_adjustment',0) for f in partials)
        total_net=net_pnl(total_gross,total_fees,total_funding)+total_adjustment
        weighted_exit=(price*quantity+sum(f['price']*f['quantity'] for f in partials))/total_quantity
        closed={**p,'quantity':total_quantity,'entry_fee':p.get('original_entry_fee',p['entry_fee']),
                'initial_margin':p.get('original_initial_margin',initial_margin),'planned_risk':p.get('initial_planned_risk',p['planned_risk']),
                'remaining_risk':0.,'exit':weighted_exit,'final_exit':price,'gross':total_gross,
                'net':total_net,'fees':total_fees,'funding':total_funding,'closed_at':at,'reason':reason,
                'final_fill':fill,'exit_status':'Kapandı','liquidated':reason=='Tahmini tasfiye',
                'settlement_adjustment':total_adjustment}
        # The final trade-result receipt is the final slice only; the closed
        # record and feedback aggregate every slice. Fee/funding rows remain
        # separate reconciliation records and must not be added to trade net.
        self.state['positions'] = [r for r in self.state['positions'] if r['id']!=id]
        self.state['closed'].append(closed)
        self.record_feedback(closed)
        self.audit('exit',f"{p['symbol']} kapandı · toplam net {total_net:+.2f} USDT",closed)
        self.save()
        return dict(ok=True,message=f'Sanal pozisyon kapandı: {total_net:+.2f} USDT',receipt=receipt)

    def record_feedback(self,position):
        if self.mode!='PAPER' or position.get('sample') or position.get('origin')=='chat' or len(position.get('features',[]))!=19 or not position.get('closed_at'):return
        records=self.store.get('adaptive_feedback',[])
        record=dict(id=position['id'],venue=position['venue'],symbol=position['symbol'],market=position['market'],
                    strategy=position['strategy'],method=position['method'],model_version=position.get('model_version'),
                    features=position['features'],candle_time=position['candle_time'],opened_at=position['opened_at'],
                    closed_at=position['closed_at'],net=position['net'],r=position['net']/max(position.get('initial_planned_risk',position['planned_risk']),1e-9))
        records=[r for r in records if r['id']!=record['id']]+[record]
        self.store.set('adaptive_feedback',records[-3000:])

    def feedback(self,key):
        venue,symbol,market,strategy=key.split(':')
        return [r for r in self.store.get('adaptive_feedback',[]) if
                (r['venue'],r['symbol'],r['market'],r['strategy'])==(venue,symbol,market,strategy)]

    def check_positions(self):
        for p in list(self.state['positions']):
            q = self.quote(p['venue'],p['symbol'],p['market'])
            if not q or not all(math.isfinite(q.get(k,0)) and q.get(k,0)>0 for k in ('price','bid','ask')) or q['bid']>q['ask'] or time.time()-q['observed']>30: continue
            mark=q.get('mark_price') if p['market']=='futures' else q['price']
            mark_fresh=bool(mark) and math.isfinite(mark) and mark>0 and time.time()-q.get('mark_price_observed',q['observed'] if self.mode=='DEMO' else 0)<=15
            p['price'] = mark if mark_fresh else q['price']
            side = 1 if p['side']=='long' else -1
            price=executable_price(p,q)
            if p['market']=='futures' and mark_fresh and margin_status(p,mark)['liquidatable']:
                self.close_position(p['id'],'Tahmini tasfiye')
            elif side*(price-p['stop'])<=0: self.close_position(p['id'],'Stop')
            elif side*(price-p['target'])>=0: self.close_position(p['id'],'Hedef')
            elif time.time()-p['opened_at'] > (16*900 if p['strategy']=='intraday' else 42*14400):
                self.close_position(p['id'],'Süre sınırı')
            elif self.mode=='PAPER' and all(time.time()-q.get(k+'_observed',q['observed'])<=15 for k in ('bid','ask')):
                action=adaptive_action(p,price)
                if action=='partial': self.partial_position(p['id'])
                elif action=='trail':
                    before=copy.deepcopy(self.state)
                    try:
                        with self.store.atomic():
                            if tighten_stop(p,price):
                                self.audit('trailing_stop',f"{p['symbol']} takip stopu güncellendi.",dict(id=p['id'],stop=p['stop']))
                                self.save()
                    except Exception:
                        self.states[self.mode]=before
                        raise
        if hasattr(self,'operations'):self.operations.enforce()
        equity = self.equity()
        if self.state['day']!=self.day():
            self.state['day'],self.state['day_equity']=self.day(),equity
            if self.state['halt'].startswith('Günlük'): self.state['halt']=''
        self.state['peak']=max(self.state['peak'],equity)
        daily=(equity/self.state['day_equity']-1)*100
        dd=(1-equity/self.state['peak'])*100
        if dd>=self.settings.drawdown:
            self.state['halt']='Hesap düşüşü sınırı; manuel inceleme gerekiyor.'
            self.state['running']=False
            for p in list(self.state['positions']): self.close_position(p['id'],'Hesap düşüşü risk çıkışı')
        elif daily<=-self.settings.daily_loss:
            self.state['halt']='Günlük kayıp sınırı; yeni girişler ertelendi.'
            self.state['running']=False

    def apply_funding(self,quote):
        if quote['market']!='futures' or not quote.get('settlements'): return
        before=copy.deepcopy(self.state)
        try:
            with self.store.atomic():
                changed=False
                for p in self.state['positions']+self.state['closed']:
                    if p['market']!='futures' or p['venue']!=quote['venue'] or p['symbol']!=quote['symbol'] or 'opened_at' not in p:
                        continue
                    for event in quote.get('settlements',[]):
                        if not p['opened_at']<=event['time']<=p.get('closed_at',time.time()): continue
                        id=f"{p['id']}:funding:{int(event['time'])}"
                        price=event.get('mark') or quote['price']
                        quantity=quantity_at(p,event['time'])
                        amount=-(1 if p['side']=='long' else -1)*quantity*price*event['rate']
                        if quantity<=0:continue
                        if self.store.ledger(id,self.mode,'funding',amount,dict(position_id=p['id'],quantity=quantity,settlement=event,estimated_mark=not bool(event.get('mark')))):
                            allocated=0.
                            correction=0.
                            def allocate(fill, share):
                                previous=fill.get('settlement_adjustment',0.)
                                fill['funding']+=share
                                margin=fill.get('initial_margin',p.get('original_initial_margin',p.get('initial_margin',p['entry']*p['quantity']/p['leverage']))*fill['quantity']/p.get('original_quantity',p['quantity']))
                                adjustment=isolated_adjustment(margin,fill['funding'],fill['gross'],fill['exit_fee'],fill['reason'])
                                fill['settlement_adjustment']=adjustment
                                fill['net']+=share+adjustment-previous
                                return adjustment-previous
                            for fill in p.get('partial_fills',[]):
                                if event['time']<=fill['closed_at']:
                                    share=amount*fill['quantity']/quantity
                                    correction+=allocate(fill,share)
                                    allocated+=share
                            p['partial_realized']=sum(f['net'] for f in p.get('partial_fills',[]))
                            if 'net' in p:
                                p['funding']+=amount
                                if not p.get('final_fill'):
                                    # Legacy complete closes have no per-slice receipt in state.
                                    p['final_fill']=dict(quantity=p['quantity'],gross=p['gross'],
                                        exit_fee=p['fees']-p['entry_fee'],funding=p['funding']-amount,
                                        net=p['net'],reason=p['reason'],initial_margin=p.get('initial_margin',p['entry']*p['quantity']/p['leverage']),
                                        settlement_adjustment=p.get('settlement_adjustment',0.))
                                correction+=allocate(p['final_fill'],amount-allocated)
                                p['net']+=amount+correction
                                p['settlement_adjustment']=p.get('settlement_adjustment',0.)+correction
                                self.record_feedback(p)
                            else:p['funding']+=amount-allocated
                            if correction:
                                self.store.ledger(id+':isolated_correction',self.mode,'isolated_funding_correction',correction,dict(position_id=p['id'],settlement=event))
                            self.state['wallets'][f"{p['venue']}:futures"]+=amount+correction
                            self.state['funding']+=amount
                            changed=True
                if changed:self.save()
        except Exception:
            self.states[self.mode]=before
            raise

    async def start(self):
        self.tasks=[asyncio.create_task(self.heartbeat(),name='pozisyon kontrolü'),asyncio.create_task(self.prices(),name='piyasa uzlaştırması'),
                    asyncio.create_task(self.scan(),name='strateji taraması'),asyncio.create_task(self.training.run(),name='arka plan eğitimi'),
                    asyncio.create_task(self.dispatch_entries(),name='giriş kontrolü'),asyncio.create_task(self.news_loop(),name='haber takibi'),asyncio.create_task(self.local_ai_loop(),name='AI koordinasyonu')]
        for venue,market,channel in [('Binance','spot','market'),('Binance','futures','market'),
                                      ('Binance','futures','book'),('Bybit','spot','market'),('Bybit','futures','market')]:
            self.tasks.append(asyncio.create_task(listen(venue,market,channel,
                lambda v=venue,m=market:self.universe.streams(self,v,m) if self.mode=='PAPER' else [],self.stream_update,lambda:self.closing)))
        for task in self.tasks:task.add_done_callback(self.background_task_done)

    def background_task_done(self,task):
        if self.closing:return
        error=None if task.cancelled() else task.exception()
        # Every registered task is a long-lived loop; unexpected normal returns
        # also invalidate the engine's claim that its protective services run.
        message=f'Arka plan görevi durdu ({task.get_name()}); yeni girişler kapatıldı. Uygulamayı tamamen yeniden açın.'
        self.state['running']=False
        self.state['halt']=self.state['halt'] or message
        self.state['engine_fault']=message
        async def persist():
            try:
                async with self.lock:
                    self.audit('engine_fault',message,dict(error_type=type(error).__name__ if error else 'unexpected_stop'))
                    self.save()
            except Exception:pass
        self.tasks.append(asyncio.create_task(persist()))

    async def stream_update(self,update):
        async with self.lock:
            if self.mode!='PAPER' or update['symbol'] not in self.settings.allowlist: return
            q=self.quote(update['venue'],update['symbol'],update['market'])
            if not q:
                q=dict(symbol=update['symbol'],venue=update['venue'],market=update['market'],observed=0)
                self.state['markets'].append(q)
            for key,value in update.items():
                if key.endswith('_observed') and value<q.get(key,0): continue
                if key in ('price','bid','ask','mark_price') and update.get(key+'_observed',0)<q.get(key+'_observed',0): continue
                q[key]=value
            # A partially bootstrapped book cannot be treated as an executable quote.
            if all(q.get(k,0)>0 for k in ('price','bid','ask')):
                q['transport']='websocket'
                if time.monotonic()-self.stream_last_check>.2:
                    self.stream_last_check=time.monotonic()
                    self.check_positions()

    async def stop(self):
        self.closing=True
        async with self.lock:
            self.state['running']=False
            self.store.set('adaptive_controllers',self.controllers)
            self.save()
        for task in self.tasks: task.cancel()
        self.local_ai.stop()
        await asyncio.gather(*self.tasks,return_exceptions=True)
        if self.learning_pool:
            workers=list((getattr(self.learning_pool,'_processes',None) or {}).values())
            self.learning_pool.shutdown(wait=False,cancel_futures=True)
            for worker in workers:
                if worker.is_alive():worker.terminate()
                worker.join(timeout=1)

    async def heartbeat(self):
        while not self.closing:
            async with self.lock:
                self.tick+=1
                self.last_heartbeat=time.time()
                if self.mode=='DEMO':
                    for q in self.state['markets']:
                        base=76984.6 if q['symbol']=='BTCUSDT' else 2894.72
                        base*=1.00015 if q['venue']=='Bybit' else 1
                        base*=1.0003 if q['market']=='futures' else 1
                        q['price']=base*(1+math.sin(self.tick/24)*0.0005)
                        q['bid'],q['ask']=q['price']*.99995,q['price']*1.00005
                        q['observed']=time.time()
                self.check_positions()
                if self.mode=='PAPER':tick_trials(self.state)
                if self.tick%10==0:
                    if self.controllers_dirty:
                        self.store.set('adaptive_controllers',self.controllers)
                        self.controllers_dirty=False
                    self.state['equity_curve'].append(dict(time=int(time.time()),value=round(self.equity(),2)))
                    self.state['equity_curve']=self.state['equity_curve'][-1000:]
                    self.save()
            await asyncio.sleep(1)

    async def prices(self):
        while not self.closing:
            if self.mode=='PAPER':
                if self.settings.auto_universe and self.universe.due():
                    await self.refresh_universe()
                symbols=self.settings.allowlist.copy()
                exposed_products={(p['venue'],p['symbol'],p['market']) for p in self.state['positions']}
                async def batch(venue,market):
                    wanted=[s for s in symbols if not self.settings.auto_universe or not self.universe.catalogs or self.universe.supports(venue,s,market) or (venue,s,market) in exposed_products]
                    if not wanted:return []
                    try:return await asyncio.to_thread(Exchange(venue).quotes,wanted,market)
                    except Exception:return []
                batches=await asyncio.gather(*(batch(v,m) for v in ('Binance','Bybit') for m in ('spot','futures')))
                results=[q for rows in batches for q in rows]
                # Settlement history is fetched only for exposed paper positions
                # and active reference trials, never for every idle watchlist coin.
                exposed={(p['venue'],p['symbol'],'futures') for p in self.state['positions'] if p['market']=='futures'}
                exposed.update((t['venue'],t['symbol'],'futures') for t in self.state.get('adaptive_trials',[]) if t.get('market')=='futures' and (not t.get('closed_at') or not t.get('funding_complete')))
                exposed.update((t['venue'],t['symbol'],'futures') for t in self.state['closed'] if t['market']=='futures' and time.time()-t['closed_at']<86400)
                async def settle(key):
                    cache=self.funding_cache.get(key)
                    if not cache or time.time()-cache[0]>120:
                        try:
                            cache=(time.time(),await asyncio.to_thread(Exchange(key[0]).funding_events,key[1]))
                            self.funding_cache[key]=cache
                        except Exception:pass
                    return key,cache
                settlements=dict(await asyncio.gather(*(settle(k) for k in exposed)))
                for q in results:
                    if q['market']!='futures':continue
                    cache=settlements.get((q['venue'],q['symbol'],q['market']))
                    q.update(settlements=cache[1] if cache else [],funding_status='observed' if cache else 'unknown',funding_checked=cache[0] if cache else 0)
                async with self.lock:
                    if self.mode=='PAPER':
                        valid=[r for r in results if r]
                        for q in valid:
                            if q['symbol'] not in self.settings.allowlist:continue
                            old=self.quote(q['venue'],q['symbol'],q['market'])
                            if old:
                                # Slow REST responses must not overwrite newer stream fields.
                                for key in ('price','bid','ask','mark_price'):
                                    if old.get(key+'_observed',0)>q.get(key+'_observed',0):
                                        q[key]=old[key]
                                        q[key+'_observed']=old[key+'_observed']
                                        if key=='price':q['price_transport']=old.get('price_transport','websocket')
                                q['observed']=max(q['observed'],old.get('observed',0))
                                q.update({k:old[k] for k in ('stream_observed','transport') if k in old})
                                old.update(q)
                            else:self.state['markets'].append(q)
                            self.apply_funding(q)
                        expected=sum(self.universe.supports(v,s,m) for v,m in PRODUCTS for s in symbols) if self.settings.auto_universe and self.universe.catalogs else len(symbols)*4
                        self.state['source_status']='ok' if len(valid)>=expected and expected else 'partial' if valid else 'unavailable'
                        now=time.time()
                        if valid:
                            if self.state['last_tick'] and now-self.state['last_tick']<45:
                                self.state['accumulated_seconds']+=min(now-self.state['last_tick'],15)
                            self.state['last_tick']=now
                            if self.day() not in self.state['paper_days']: self.state['paper_days'].append(self.day())
                        self.save()
            await asyncio.sleep(10)

    async def refresh_universe(self):
        if self.universe.loading:return
        self.universe.loading=True
        async def discover(venue,market):
            try:return venue,market,await asyncio.to_thread(Exchange(venue).catalog,market),''
            except Exception:return venue,market,[], 'unavailable'
        try:
            results=await asyncio.gather(*(discover(v,m) for v,m in PRODUCTS))
            async with self.lock:
                if self.closing:return
                previous=copy.deepcopy(self.universe)
                try:
                    with state_transaction(self):
                        self.universe.merge(results)
                        self.store.set('exchange_universe',self.universe.saved())
                        if self.settings.auto_universe and self.mode=='PAPER':
                            symbols=self.universe.selection(self)
                            if symbols:
                                self.settings=RiskSettings(**{**self.settings.model_dump(),'allowlist':symbols})
                                self.store.set('settings',self.settings.model_dump())
                                allowed=set(symbols)
                                self.state['markets']=[q for q in self.state['markets'] if q['symbol'] in allowed]
                                for name in ('decisions','learning','regimes'):
                                    self.state[name]={k:v for k,v in self.state.get(name,{}).items() if v.get('symbol',k.split(':')[1] if ':' in k else '') in allowed}
                                self.audit('universe',f'{len(symbols)} USDT paritesi analiz havuzuna alındı; hesap ve risk sınırları korundu.')
                                self.scan_wake.set()
                                self.save()
                except BaseException:
                    self.universe=previous
                    self.universe.refresh_requested=True
                    raise
        finally:self.universe.loading=False

    def candles(self,symbol,interval,venue='Binance',market='spot',full=False,mode=None):
        mode=mode or self.mode
        key=(mode,venue,symbol,interval,market)
        item=self.cache.get(key)
        if not item and mode=='PAPER' and self.settings.auto_universe:
            item=scanner_cache.load(self,key)
        step={'15m':900,'1h':3600,'4h':14400,'1d':86400}[interval]
        if item and (time.time()-item[0]<45 or (item[1] and item[1][-1]['time']+step>=int(time.time())//step*step)):
            rows=item[1]
        elif mode=='DEMO':
            rows=demo_candles(symbol,interval,1500 if interval!='4h' else 1600)
            self.cache[key]=(time.time(),rows)
        else:
            exchange=Exchange(venue)
            rows=exchange.candles(symbol,interval,market,1000)
            if item:rows=sorted({r['time']:r for r in item[1]+rows}.values(),key=lambda r:r['time'])[-4000:]
            if interval=='4h' and rows and len(rows)<1500:
                older=exchange.candles(symbol,interval,market,1000,end=rows[0]['time']-1)
                rows=sorted({r['time']:r for r in older+rows}.values(),key=lambda r:r['time'])
            self.cache[key]=(time.time(),rows)
        if full and mode=='PAPER' and interval in ('15m','4h') and key not in self.history_bootstrapped:
            exchange=Exchange(venue)
            for _ in range(3):
                if not rows or len(rows)>=3900:break
                try:older=exchange.candles(symbol,interval,market,1000,end=rows[0]['time']-1)
                except Exception:break
                if not older:break
                rows=sorted({r['time']:r for r in older+rows}.values(),key=lambda r:r['time'])[-4000:]
            self.history_bootstrapped.add(key)
            self.cache[key]=(time.time(),rows)
        if mode=='PAPER' and self.settings.auto_universe:
            if full and (not item or rows is not item[1]):
                scanner_cache.save(self,key,rows)
            # Disk history survives rotation; quote/position protection is independent.
            scanner_cache.trim(self)
        return rows if full else rows[-180:]

    async def scan_one(self,mode,venue,symbol,market,strategy,defer=False):
        session_id=self.state.get('session_id')
        def active():
            return (self.mode==mode and self.state.get('session_id')==session_id and self.state['running']
                    and self.enabled.get(strategy) and symbol in self.settings.allowlist)
        if not active():return
        q=self.quote(venue,symbol,market)
        if mode=='PAPER' and (not q or q.get('volume',0)<5_000_000 or time.time()-q.get('observed',0)>30):
            return
        try:
            rows=await asyncio.to_thread(self.candles,symbol,'15m' if strategy=='intraday' else '4h',venue,market,True,mode)
            if not rows or not active():return
            cache_key=(mode,venue,symbol,market,strategy)
            cached=self.analysis_cache.get(cache_key)
            if not cached or cached[0]!=rows[-1]['time']:
                result,context=await asyncio.to_thread(analyze_candles,rows,strategy,market)
                choices=await asyncio.to_thread(options,rows,strategy,market) if mode=='PAPER' else []
                self.analysis_cache[cache_key]=(rows[-1]['time'],result,context,choices)
                if mode=='PAPER' and strategy=='intraday':self.return_history[symbol]=returns(rows[-193:])
            else:
                _,result,context,choices=cached
            async with self.lock:
                if not active():return
                if mode=='PAPER':
                    latest=self.controllers.get(f'{venue}:{symbol}:{market}:{strategy}',{}).get('latest',{})
                    if self.controllers.get(f'{venue}:{symbol}:{market}:{strategy}',{}).get('schema')!=SCHEMA or latest.get('candle_time')!=rows[-1]['time']:
                        self.training.submit(mode,session_id,f'{venue}:{symbol}:{market}:{strategy}',rows,strategy,market)
                self.commit_analysis(mode,venue,symbol,market,strategy,rows[-1]['time'],result,context,choices)
                if mode=='PAPER' and not defer:self.operations.dispatch()
        except Exception:
            async with self.lock:
                if not active():return
                self.audit('data','Strateji için yeterli/güncel veri alınamadı.',dict(venue=venue,symbol=symbol,strategy=strategy))
                self.state.setdefault('decisions',{})[f'{venue}:{symbol}:{market}:{strategy}']=dict(venue=venue,symbol=symbol,market=market,
                    strategy=strategy,observed=time.time(),regime='unavailable',block_code='unavailable',message='Piyasa geçmişine erişilemiyor; işlem açılmadı.')

    def commit_analysis(self,mode,venue,symbol,market,strategy,candle_time,result,context,choices):
        """Fast path: existing validated/statistical model only; never train here."""
        key=f'{venue}:{symbol}:{market}:{strategy}'
        context={**context,'observed':time.time()}
        learning={};controller=self.controllers.get(key,{})
        actual=self.feedback(key) if mode=='PAPER' else []
        if mode=='PAPER':
            transition=consider_promotion(controller,self.state.get('adaptive_trials',[]),key)
            if transition:self.audit('model','İleri dönem model karşılaştırması tamamlandı.',dict(key=key,**transition))
            rollback=consider_rollback(controller,actual)
            if rollback:self.audit('model','Gerçek sanal sonuçlar nedeniyle model geri alındı.',dict(key=key,**rollback))
            if controller:self.controllers[key]=controller
            register_trials(self.state,key,controller,choices,self.quote(venue,symbol,market),actual)
            result=decision(controller,choices,actual)
            learning=public_state(controller,choices,actual)
            self.state.setdefault('learning',{})[key]=learning
            self.controllers_dirty=True
        self.state.setdefault('regimes',{})[key]=context
        step=900 if strategy=='intraday' else 14400
        checks=selection_checks(controller,choices,actual) if mode=='PAPER' else []
        code='queued' if result else 'waiting_rule' if not choices else 'selector'
        message='Sinyal hızlı giriş kontrolüne hazır.' if result else 'Kapanmış mumda yöntemlerin giriş koşulu oluşmadı.' if not choices else 'Yöntem seçici girişi eledi: '+'; '.join(dict.fromkeys(c['reason'] for c in checks if c['code']!='eligible'))
        if mode=='PAPER' and not (controller.get('champion') or controller.get('latest')):
            code='preparing_model';message='İlk geçmiş değerlendirmesi arka planda hazırlanıyor; doğrulanmış model bekleniyor.'
        if context['regime']=='unavailable':code='warmup';message='Gösterge hazırlığı için yeterli geçmiş bekleniyor.'
        if context.get('data_quality')=='gap':code='data_gap';message='Son 80 mumda veri boşluğu var; yeni giriş bekliyor.'
        if context['regime']=='volatile':code='volatile';message='ATR/fiyat oranı %2,5 üstünde; yeni giriş bekliyor.'
        self.state.setdefault('decisions',{})[key]=dict(venue=venue,symbol=symbol,market=market,strategy=strategy,
            observed=time.time(),regime=context['regime'],message=message,block_code=code,
            candle_time=candle_time,next_close=(int(time.time())//step+1)*step,
            model_score=learning.get('score'),model_version=learning.get('version'),
            selected_method=result.get('method') if result else None,risk_multiplier=result.get('risk_multiplier') if result else None,
            candidates=[dict(method=c['method'],name=METHODS[c['method']],side=c['side']) for c in choices],candidate_checks=checks)
        if not result:
            for item in self.state.get('operation_candidates',{}).values():
                if (item['status']=='eligible' and ':'.join(item['id'].split(':')[:4])==key and item['candle_time']<=candle_time):
                    item.update(status='blocked',reason='Güncel yöntem seçimi bu girişe artık izin vermiyor.')
            return
        sig=Signal(strategy=strategy,symbol=symbol,venue=venue,market=market,**result)
        if mode=='PAPER':
            self.operations.publish(sig)
            item=self.state.get('operation_candidates',{}).get(self.operations.identity(sig))
            if item and item['status'] in ('opened','blocked'):
                self.state['decisions'][key].update(message=item['reason'],accepted=item['status']=='opened',block_code='opened' if item['status']=='opened' else 'risk')
        else:
            identity=self.operations.identity(sig)
            if identity not in self.state['last_signals']:
                self.state['last_signals']=(self.state['last_signals']+[identity])[-500:]
                outcome=self.open_signal(sig)
                self.state['decisions'][key].update(message=outcome['message'],accepted=outcome['ok'],block_code='opened' if outcome['ok'] else 'risk')

    async def training_completed(self,job):
        async with self.lock:
            if (self.closing or self.mode!=job.mode or self.state.get('session_id')!=job.session_id or not self.state['running']):return
            venue,symbol,market,strategy=job.key.split(':')
            if symbol not in self.settings.allowlist or not self.enabled.get(strategy):return
            cached=self.analysis_cache.get((job.mode,venue,symbol,market,strategy))
            if not cached or cached[0]!=job.candle_time:return
            self.commit_analysis(job.mode,venue,symbol,market,strategy,cached[0],cached[1],cached[2],cached[3])

    def refresh_entry_candidates(self):
        """Recheck model/feedback immediately before allocating an entry budget."""
        ready=set()
        keys={':'.join(item['id'].split(':')[:4]) for item in self.state.get('operation_candidates',{}).values() if item['status']=='eligible'}
        for key in keys:
            venue,symbol,market,strategy=key.split(':')
            if symbol not in self.settings.allowlist or not self.enabled.get(strategy):continue
            cached=self.analysis_cache.get((self.mode,venue,symbol,market,strategy))
            if not cached:continue
            ready.add(key)
            self.commit_analysis(self.mode,venue,symbol,market,strategy,cached[0],cached[1],cached[2],cached[3])
        return ready

    async def dispatch_entries(self):
        while not self.closing:
            try:
                async with self.lock:
                    if self.mode=='PAPER' and self.state['running']:
                        self.operations.dispatch()
            except asyncio.CancelledError:raise
            except Exception:
                async with self.lock:
                    self.state['running']=False
                    self.state['halt']='Giriş kaydı tamamlanamadı; yeni girişler durduruldu. Yerel kayıtları kontrol edin.'
                    try:self.audit('execution',self.state['halt']);self.save()
                    except Exception:pass
            await asyncio.sleep(1)

    async def scan(self):
        semaphore=asyncio.Semaphore(4)
        async def one(mode,request):
            async with semaphore:
                if self.mode==mode and self.state['running']:
                    await self.scan_one(mode,*request,defer=True)
        while not self.closing:
            if self.state['running']:
                mode=self.mode
                symbols=self.universe.batch(self) if mode=='PAPER' else self.settings.allowlist
                requests=[(v,s,m,st) for s in symbols for st in ('intraday','swing')
                          for v in ('Binance','Bybit') for m in ('spot','futures') if self.enabled.get(st) and (mode!='DEMO' or s in ('BTCUSDT','ETHUSDT'))
                          and (mode!='PAPER' or not self.settings.auto_universe or not self.universe.catalogs or self.universe.supports(v,s,m,fresh=True))]
                await asyncio.gather(*(one(mode,r) for r in requests))
            try:await asyncio.wait_for(self.scan_wake.wait(),timeout=15)
            except asyncio.TimeoutError:pass
            self.scan_wake.clear()

    async def news_loop(self):
        while not self.closing:
            try:
                events,sources=await asyncio.to_thread(collect_news,self.news)
                async with self.lock:
                    self.news,self.news_sources=events,sources
                    self.last_news=time.time()
                    self.store.set('news',events)
                    self.store.set('news_sources',sources)
                if self.telegram and self.settings.telegram_enabled:
                    for event in events:
                        if event['severity']=='critical' and event['id'] not in self.last_alert:
                            await self.notify(event['title']+'\n'+event['url'])
                            self.last_alert.add(event['id'])
                    daykey='digest:'+self.day()
                    if datetime.now(ZoneInfo('Europe/Istanbul')).hour>=21 and daykey not in self.last_alert:
                        await self.notify('Günlük özet\n'+ '\n'.join(e['title'] for e in events[:5]) + f'\nMod: {self.mode} · Özsermaye: {self.equity():.2f} USDT')
                        self.last_alert.add(daykey)
                    self.store.set('sent_alerts',list(self.last_alert)[-500:])
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(180)

    async def local_ai_loop(self):
        last_signature=None
        while not self.closing:
            if self.mode=='PAPER' and self.state['running'] and self.news and self.settings.local_ai_enabled and self.local_ai.available and not self.local_ai.disabled:
                signature=tuple(e['id'] for e in sorted(self.news,key=lambda e:e.get('published_at',''),reverse=True)[:4])
                if signature!=last_signature or time.time()-self.local_ai.last_analysis>3600:
                    try:
                        await run_cycle(self)
                        last_signature=signature
                    except asyncio.CancelledError:raise
                    except Exception:
                        self.local_ai.status='error'
                        self.local_ai.message='Yerel AI değerlendirmesi tamamlanamadı; eksik yanıt işleme uygulanmadı.'
            await asyncio.sleep(20 if not last_signature else 180)

    async def notify(self,text):
        from engine.market import fetch
        import urllib.parse
        if not self.telegram or not self.settings.telegram_chat_id: return False
        url='https://api.telegram.org/bot'+self.telegram+'/sendMessage?'+urllib.parse.urlencode(dict(chat_id=self.settings.telegram_chat_id,text=text[:3500]))
        try:
            await asyncio.to_thread(fetch,url)
            return True
        except Exception:
            return False

    def demo_events(self):
        return [dict(id='demo-event-1',title='Örnek: yaklaşan ekonomik açıklama',source='Demo senaryosu',
                     severity='scheduled',verification='sample',assets=['BTC','ETH'],published_at='',first_seen_at=iso_now(),
                     url='',demo=True,action='Örnek olaydır; gerçek haber veya güncel takvim bilgisi değildir.'),
                dict(id='demo-event-2',title='Örnek: ağ güncellemesi duyurusu',source='Demo senaryosu',
                     severity='info',verification='sample',assets=['ETH'],published_at='',first_seen_at=iso_now(),
                     url='',demo=True,action='Kaynak doğrulama ve olay kaydı görünümü. İşlem kısıtı uygulanmadı.')]

    def snapshot(self):
        equity=self.equity()
        usable=[r for r in self.state['markets'] if all(r.get(k,0)>0 for k in ('price','bid','ask'))]
        fresh=[r for r in usable if time.time()-r['observed']<15 and
               all(time.time()-r.get(k+'_observed',r['observed'])<15 for k in ('bid','ask'))]
        expected_quotes=sum(self.universe.supports(v,s,m) for v,m in PRODUCTS for s in self.settings.allowlist) if self.settings.auto_universe and self.universe.catalogs else len(self.settings.allowlist)*4
        source_status=self.state['source_status'] if self.mode=='DEMO' else ('ok' if len(fresh)>=expected_quotes and expected_quotes else 'partial' if fresh else 'unavailable')
        positions=[]
        for p in self.state['positions']:
            side=1 if p['side']=='long' else -1
            gross=(p.get('price',p['entry'])-p['entry'])*p['quantity']*side
            raw_gross=gross
            if p['market']=='futures':
                collateral=p.get('initial_margin',p['quantity']*p['entry']/p['leverage'])+p.get('funding',0)
                gross=max(gross,-collateral)
            q=self.quote(p['venue'],p['symbol'],p['market']) or {}
            margin=margin_status(p,q.get('mark_price') or p.get('price',p['entry']))
            executable=executable_price(p,q) if all(q.get(k,0)>0 for k in ('bid','ask')) else None
            remaining=remaining_net(p,executable) if executable is not None else None
            positions.append({**p,**margin,'unrealized':gross,'raw_unrealized':raw_gross,
                              'net_if_close':remaining+p.get('partial_realized',0) if remaining is not None else None,
                              'remaining_net_if_close':remaining,'exit_price_estimate':executable,
                              'exit_policy':p.get('exit_policy','fixed'),
                              'original_quantity':p.get('original_quantity',p['quantity']),
                              'remaining_risk':p['planned_risk'],
                              'partial_realized':p.get('partial_realized',0),
                              'exit_status':p.get('exit_status','Sabit stop ve hedef'),
                              'mark_fresh':time.time()-q.get('mark_price_observed',0)<15})
        fees=self.state['fees']
        open_risk=sum(p['planned_risk'] for p in positions)
        active_groups=[g for g in self.state['groups'] if g['status'] not in ('closed','cancelled')]
        open_risk+=sum(g.get('planned_risk',0) for g in active_groups)
        return dict(mode=self.mode,running=self.state['running'],halt=self.state['halt'],
                    metrics=dict(equity=equity,net=equity-self.state['initial'],net_pct=(equity/self.state['initial']-1)*100,
                                 daily=(equity/self.state['day_equity']-1)*100,open_risk=open_risk,
                                 risk_pct=open_risk/max(equity,1)*100,drawdown=max(0,(1-equity/self.state['peak'])*100),
                                 fees=fees,funding=self.state['funding'],initial=self.state['initial'],
                                 closed_count=len(self.state['closed']),liquidations=sum(bool(t.get('liquidated')) for t in self.state['closed']),
                                 realized=sum(t['net'] for t in self.state['closed'])+sum(p.get('partial_realized',0) for p in positions),
                                 win_rate=sum(t['net']>0 for t in self.state['closed'])/max(1,len(self.state['closed']))*100),
                    positions=positions,closed=list(reversed(self.state['closed'][-100:])),groups=list(reversed(self.state['groups'][-20:])),
                    markets=usable,curve=self.state['equity_curve'],settings=self.settings.model_dump(),
                    decisions=list(self.state.get('decisions',{}).values()),execution=execution_snapshot(self),
                    learning=[dict(key=k,**{field:value for field,value in r.items() if field not in ('coefficients','intercept')}) for k,r in self.state.get('learning',{}).items()],
                    local_ai={**self.local_ai.snapshot(),'enabled':self.settings.local_ai_enabled,'report':self.ai_report,
                              'experiments':self.store.get('local_ai_experiments',[])[-5:]},
                    session=dict(id=self.state.get('session_id'),started_at=self.state['started_at'],seconds=self.state['accumulated_seconds']),
                    strategies=[dict(**c,enabled=self.enabled.get(c['id'],False)) for c in CATALOG],knowledge=library_snapshot(),
                    news=self.demo_events() if self.mode=='DEMO' else self.news,news_sources=self.news_sources,
                    connections=list(self.connections.values()),jobs=self.jobs,reports=[self.report_preview(r) for r in self.reports],
                    audit=self.store.audit_list(self.mode),source_status=source_status,
                    live_gate=self.live_gate(),timestamp=time.time(),paper_days=len(self.states['PAPER']['paper_days']),
                    costs_estimated=True,version='0.8.0',allocation=self.allocation(),risk_profiles=PROFILES,
                    universe=self.universe.snapshot(self))

    def report_preview(self,r):
        return {**{k:v for k,v in r.items() if k not in ('training_trades','trades','curve')},
                'needs_retest':r.get('execution_model')!='bar-causal-v2'}

    def allocation(self):
        weights={}
        for c in CATALOG[:2]:
            if not self.enabled.get(c['id']):weights[c['id']]=0;continue
            contexts=[r for key,r in self.state.get('regimes',{}).items() if key.endswith(':'+c['id']) and time.time()-r['observed']<300]
            scores=[1 if r['regime'] in ('uptrend','downtrend') else .25 if r['regime']=='range' else 0 for r in contexts]
            weights[c['id']]=sum(scores)/len(scores) if scores else 1
        total=sum(weights.values())
        return [dict(strategy=c['id'],share=round(min(50,weights[c['id']]/total*100),1) if total else 0,
                     ceiling=1.0,reason='Rejim uyumu ile sınırlı sanal dağıtım; artan bütçe zorla kullanılmaz.' if weights[c['id']] else 'Etkin değil veya rejim uygun değil.') for c in CATALOG[:2]]

    def live_gate(self):
        days=len(self.states['PAPER']['paper_days'])
        checks=[dict(name='Hesap anahtarları ve ürün izinleri',ok=all(c['authenticated'] for c in self.connections.values())),
                dict(name='Bağımsız gerçek veri / hesap komisyonu doğrulaması',ok=False),
                dict(name='En az 100 bağımsız test işlemi, pozitif net, düşüş ≤ %10',ok=False),
                dict(name=f'En az 30 gün sanal izleme ({days}/30)',ok=days>=30 and self.states['PAPER']['accumulated_seconds']>=30*86400),
                dict(name='Canlı emir ve koruyucu stop entegrasyonunun ayrı kabulü',ok=False)]
        return dict(allowed=False,checks=checks,reason='Canlı ve borsa test emirleri bu araştırma sürümünde kilitli. Hiçbir API anahtarı bu kilidi kaldırmaz.')

    async def command(self,kind,payload):
        async with self.lock:
            if self.closing:return dict(ok=False,message='Motor kapanıyor; komut uygulanmadı.')
            try:
                # SQLite backup must run after commits, never inside a write
                # transaction on its source connection.
                if kind=='backup':
                    self.store.set('adaptive_controllers',self.controllers)
                    self.save()
                    return dict(ok=True,message='Veritabanı yedeklendi.',path=self.store.backup())
                with state_transaction(self):
                    result=self._command(kind,payload)
                    self.save()
                    return result
            except Exception:
                return dict(ok=False,message='Komut kaydedilemedi; hesap, mod ve ayarlar önceki durumuna alındı.')

    def _command(self,kind,payload):
        if kind=='paper_session':
            try: validated=RiskSettings(**{**self.settings.model_dump(),'paper_balance':payload.get('balance',10000)})
            except (ValueError,TypeError):return dict(ok=False,message='Sanal bakiye 100–10.000.000 USDT arasında olmalı.')
            if self.states['PAPER']['positions'] or self.state['positions']:
                return dict(ok=False,message='Yeni oturumdan önce açık sanal pozisyonları kapatın veya mevcut oturumu sürdürün.')
            if any(g['status'] not in ('closed','cancelled') for g in self.state['groups']):
                return dict(ok=False,message='Önce açık işlem gruplarını kapatın.')
            with self.store.atomic():
                self.state['running']=False
                self.save()
                old=self.states['PAPER']
                self.store.set('archive:paper:'+old.get('session_id',uuid.uuid4().hex),old)
                self.settings=validated
                self.store.set('settings',self.settings.model_dump())
                self.mode='PAPER'
                self.states['PAPER']=self.new_state('PAPER')
                self.state['running']=True
                self.state['started_at']=time.time()
                self.audit('session',f'{self.settings.paper_balance:.2f} USDT ile gerçek verili sanal oturum başladı. Uyarlanabilir strateji seçicisi etkin.')
                self.save()
            self.scan_wake.set()
            return dict(ok=True,message='Sanal oturum başladı. Gerçek fiyatlar alınıyor; bot koşullar oluşunca kendisi işlem açacak.')
        if kind=='mode':
            mode=payload.get('mode')
            if mode not in ('DEMO','PAPER'):
                return dict(ok=False,message=self.live_gate()['reason'])
            if self.state['positions'] or any(g['status'] not in ('closed','cancelled') for g in self.state['groups']):
                return dict(ok=False,message='Mod değiştirmeden önce açık sanal pozisyon/grupları kapatın.')
            self.state['running']=False
            self.save()
            self.mode=mode
            self.state['running']=False
            self.save()
            return dict(ok=True,message='Demo modu açıldı.' if mode=='DEMO' else 'Sanal mod: gerçek fiyatlar alınıyor; işlemler sanaldır.')
        if kind=='start':
            if self.state['halt']: return dict(ok=False,message=self.state['halt'])
            self.state['running']=True
            self.state['started_at']=self.state['started_at'] or time.time()
            self.audit('start','Sanal strateji motoru başlatıldı.')
            self.scan_wake.set()
        elif kind=='pause':
            self.state['running']=False
            self.audit('pause','Yeni girişler durduruldu; sanal stop takibi devam ediyor.')
        elif kind=='risk_profile':
            profile=payload.get('profile')
            if profile not in PROFILES:return dict(ok=False,message='Geçersiz risk profili.')
            values={k:v for k,v in PROFILES[profile].items() if k!='name'}
            self.settings=RiskSettings(**{**self.settings.model_dump(),**values,'risk_profile':profile})
            self.store.set('settings',self.settings.model_dump())
            self.audit('settings',PROFILES[profile]['name']+' sanal risk profili seçildi; yeni girişlere uygulanır.')
        elif kind=='close':
            return self.close_position(payload.get('id',''))
        elif kind=='close_all':
            self.state['running']=False
            results=[self.close_position(p['id']) for p in list(self.state['positions'])]
            if any(not r['ok'] for r in results): return dict(ok=False,message='Bazı pozisyonlar güncel fiyat bekliyor.')
        elif kind=='demo_signal':
            if self.mode!='DEMO': return dict(ok=False,message='Örnek sinyal yalnız Demo modunda kullanılabilir.')
            if not self.state['running']: return dict(ok=False,message='Önce sanal motoru başlatın.')
            symbol=payload.get('symbol','BTCUSDT')
            venue=payload.get('venue','Binance')
            market=payload.get('market','futures')
            q=self.quote(venue,symbol,market)
            if not q: return dict(ok=False,message='Demo piyasası bulunamadı.')
            return self.open_signal(Signal(strategy='intraday',symbol=symbol,venue=venue,market=market,side='long',
                price=q['price'],stop=q['price']*.988,target=q['price']*1.024,reason='Kullanıcının başlattığı etiketli Demo sinyali.',candle_time=int(time.time())))
        elif kind=='strategy':
            id=payload.get('id')
            if id not in ('intraday','swing'): return dict(ok=False,message='Bu yöntem araştırma/simülasyon kataloğundadır; otomatik işlem için onaylı değildir.')
            self.enabled[id]=bool(payload.get('enabled'))
            self.store.set('enabled',self.enabled)
        elif kind=='reset':
            if any(g['status'] not in ('closed','cancelled') for g in self.state['groups']):return dict(ok=False,message='Önce açık işlem gruplarını kapatın.')
            if self.state['positions']: return dict(ok=False,message='Önce açık sanal pozisyonları kapatın.')
            self.states[self.mode]=self.new_state(self.mode)
            self.audit('reset','Sanal hesap yeniden oluşturuldu; eski muhasebe kayıtları denetim günlüğünde korunur.')
        elif kind=='news_restrict':
            id=payload.get('id')
            event=next((n for n in self.news if n['id']==id),None)
            if not event: return dict(ok=False,message='Olay bulunamadı.')
            event['restriction_until']=time.time()+1800 if payload.get('enabled',True) else 0
            event['action']='Kullanıcı doğruladı: 30 dakika yeni giriş kısıtı.' if event['restriction_until'] else 'Kısıt kaldırıldı.'
            self.store.set('news',self.news)
            self.audit('news','Olay kısıtı güncellendi.',dict(id=id))
        elif kind=='backup':
            self.save()
            return dict(ok=True,message='Veritabanı yedeklendi.',path=self.store.backup())
        elif kind=='scenario':
            if self.mode!='DEMO': return dict(ok=False,message='Arıza senaryosu yalnız Demo modunda çalışır.')
            scenario=payload.get('scenario','partial')
            group=GroupMachine(uuid.uuid4().hex,0.01)
            group.fill('buy','demo-buy-1',0.01)
            if scenario=='unknown': group.unknown('sell')
            elif scenario=='partial': group.fill('sell','demo-sell-1',0.006)
            else: group.fill('sell','demo-sell-1',0.01)
            record=dict(id=group.id,kind='spot_spot',symbol='BTCUSDT',status=group.state,legs=group.legs,
                        planned_risk=0,scenario=True,reservation_retained=not group.can_release,
                        note='Arıza simülasyonu; para/emir hareketi yok. Bilinmeyen emir yeniden gönderilmez.',created_at=time.time())
            self.state['groups'].append(record)
            return dict(ok=True,message='Emir grubu senaryosu çalıştırıldı.',group=record)
        elif kind=='clear_scenarios':
            self.state['groups']=[g for g in self.state['groups'] if not g.get('scenario')]
        else:
            return dict(ok=False,message='Bilinmeyen komut.')
        self.save()
        return dict(ok=True,message='İşlem tamamlandı.')
