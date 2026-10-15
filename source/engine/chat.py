"""Persistent local conversation; only deterministic, user-confirmed actions mutate paper state."""
from __future__ import annotations

import asyncio
import copy
import math
import re
import time
import uuid
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from engine.knowledge import research_context,history_context
from engine.models import Signal


def normalized(text):
    text=text.lower().translate(str.maketrans('çğıöşü', 'cgiosu'))
    return ''.join(c for c in unicodedata.normalize('NFKD',text) if unicodedata.category(c)!='Mn').strip()


def money(value):
    return f'{value:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def stamp(value):
    return datetime.fromtimestamp(value,ZoneInfo('Europe/Istanbul')).strftime('%d.%m.%Y %H:%M:%S')


SYMBOL_ALIASES={'BITCOIN':'BTCUSDT','ETHEREUM':'ETHUSDT','ETHER':'ETHUSDT','SOLANA':'SOLUSDT','DOGECOIN':'DOGEUSDT'}


def symbols_in(text,allowlist):
    words=set(re.findall(r'[A-Z0-9]+',text.upper()))
    return [s for s in allowlist if s in words or s[:-4] in words or any(alias in words and target==s for alias,target in SYMBOL_ALIASES.items())]


def symbol_in(text,allowlist):
    found=symbols_in(text,allowlist)
    # Common Turkish apostrophe suffixes tokenize into base symbol + suffix.
    return found[0] if len(found)==1 else None


def close_scope(text,allowlist):
    """Accept a small, explicit close grammar; never turn unknown filters into all."""
    n=normalized(text)
    symbols=symbols_in(text,allowlist)
    words=re.findall(r'[a-z0-9]+',n)
    venues=[v for v in ('Binance','Bybit') if v.lower() in words]
    markets=[m for m,terms in [('spot',('spot',)),('futures',('vadeli','futures'))] if any(t in words for t in terms)]
    sides=[s for s in ('long','short') if s in words]
    if len(symbols)>1 or len(venues)>1 or len(markets)>1 or len(sides)>1:
        return None
    permitted={'lutfen','benim','mevcut','acik','tum','butun','hepsi','hepsini','bir','olan',
               'binance','bybit','spot','vadeli','futures','long','short','kapat','kapatir','misin',
               'de','da','te','ta','ki','deki','daki','hesabimdaki'}
    permitted.update(s.lower() for s in allowlist)
    permitted.update(s[:-4].lower() for s in allowlist)
    permitted.update(alias.lower() for alias,target in SYMBOL_ALIASES.items() if target in allowlist)
    if any(w not in permitted and not w.startswith(('pozisyon','islem')) for w in words):
        return None
    if not symbols and not any(w in words for w in ('tum','butun','hepsi','hepsini')):
        return None
    return dict(symbol=symbols[0] if symbols else None,venue=venues[0] if venues else None,
                market=markets[0] if markets else None,side=sides[0] if sides else None)


def supported_mission_request(text):
    """The current mandate covers the combined universe; narrower scopes need UI/API support."""
    n=normalized(text)
    n=re.sub(r'(?<![\d.,])\d+(?:[.,]\d+)?\s*(?:usdt|usd|dolar|\$)', ' ',n)
    n=re.sub(r'\b\d+\s*x\b',' ',n)
    permitted={'ile','butceyle','butce','butcemle','piyasayi','piyasalari','piyasa','piyasada',
               'tara','tarayip','firsat','ara','bul','gorev','baslat','lutfen','tum','butun',
               'kripto','coinleri','otomatik','sanal','olarak','bir','islem','yap'}
    return all(w in permitted for w in re.findall(r'[a-z0-9]+',n))


class ChatService:
    def __init__(self,engine):
        self.engine=engine
        self.messages=engine.store.get('chat_messages',[])[-120:]
        self.plans=engine.store.get('chat_plans',[])[-60:]
        self.task=None
        self.closing=False
        for message in self.messages:
            if message.get('status')=='pending':
                message.update(status='error',content='Önceki yanıt uygulama kapatılırken tamamlanamadı. Mesajını tekrar gönderebilirsin.')
        for plan in self.plans:
            if plan['status']=='proposed':plan['status']='expired'
        self.save()

    def save(self):
        self.messages=self.messages[-120:];self.plans=self.plans[-60:]
        self.engine.store.set('chat_messages',self.messages)
        self.engine.store.set('chat_plans',self.plans)

    def snapshot(self):
        visible=copy.deepcopy(self.messages)
        for message in visible:
            message['actions']=[dict(id=p['id'],label=p['label'],kind=p['kind'],status='expired' if p['status']=='proposed' and p['expires_at']<time.time() else p['status'],
                                     summary=p['summary'],expires_at=p['expires_at'])
                                for p in self.plans if p['message_id']==message['id']]
        return dict(messages=visible,busy=bool(self.task and not self.task.done()),
                    model={**self.engine.local_ai.snapshot(),'enabled':self.engine.settings.local_ai_enabled})

    def submit(self,text):
        if self.closing or self.engine.closing:return dict(ok=False,message='Motor kapanıyor; yeni sohbet isteği alınamıyor.')
        if self.task and not self.task.done():return dict(ok=False,message='Önce devam eden yanıtın tamamlanmasını bekle.')
        if not text.strip() or len(text)>2000:return dict(ok=False,message='Mesaj 1–2000 karakter arasında olmalı.')
        now=time.time();id=uuid.uuid4().hex
        self.messages.extend([dict(id=uuid.uuid4().hex,role='user',content=text.strip(),created_at=now,status='done'),
                              dict(id=id,role='assistant',content='',created_at=now,status='pending')])
        self.save()
        self.task=asyncio.create_task(self.respond(id,text.strip()))
        return dict(ok=True,id=id)

    async def stop(self):
        self.closing=True
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)

    def answer(self,id,text,kind='records',**metadata):
        message=next((m for m in self.messages if m['id']==id),None)
        if message is None:return
        message.update(content=text,status='done',kind=kind,context_at=metadata.pop('data_at',time.time()),**metadata)
        self.save()

    def plan(self,message_id,kind,label,summary,payload=None):
        p=dict(id=uuid.uuid4().hex,message_id=message_id,kind=kind,label=label,summary=summary,
               payload=payload or {},expires_at=time.time()+120,status='proposed',mode=self.engine.mode,
               session_id=self.engine.state.get('session_id'))
        self.plans.append(p)
        return p

    def mission_plan(self,payload,message_id=None):
        e=self.engine
        reason=e.operations.validate(payload)
        if reason:return dict(ok=False,message=reason)
        id=message_id or uuid.uuid4().hex
        summary=(f"{money(payload['capital'])} USDT azami görev bütçesi · en fazla {payload['leverage']}x vadeli / 1x spot.\n"
                 f"En fazla {payload['max_positions']} görev pozisyonu; yeni giriş süresi {payload['duration_hours']} saat.\n"
                 f"Görev bütçesinde işlem riski en fazla %{money(e.settings.trade_risk)}, toplam açık risk %{money(e.settings.total_risk)}. Birleşik hesap sınırları da uygulanır.\n"
                 f"Günlük kayıp %{money(e.settings.daily_loss)} / düşüş %{money(e.settings.drawdown)} eşiğinde yeni görev girişleri durur; açık pozisyonların çıkışları devam eder.\n"
                 'Yalnız açık otomatik stratejilerin güncel sinyalleri karşılaştırılır. Bütçenin tamamı kullanılmak zorunda değil; kâr veya azami kayıp garantisi yoktur.\n'
                 'Onay, bu sınırlar içindeki otomatik sanal girişlere izin verir. Süre bitince/duraklatınca koruyucu çıkışlar sürer. Mevcut bakiye sıfırlanmaz. Görev dışındaki pozisyonlar hesap riskinde kalır.')
        payload={**payload,'approved_risk':{key:getattr(e.settings,key) for key in ('trade_risk','total_risk','daily_loss','drawdown')}}
        p=self.plan(id,'mission','Bütçeli sanal görevi başlat',summary,payload)
        if not message_id:self.messages.append(dict(id=id,role='assistant',created_at=time.time(),status='done',kind='plan',content='Bütçeli sanal görev önizlemesi; henüz başlamadı.',context_at=time.time()))
        self.save()
        return dict(ok=True,message='Görev planı hazır; onaylayınca otomatik sanal girişler başlayacak.',action={k:p[k] for k in ('id','label','kind','status','summary','expires_at')})

    async def respond(self,id,text):
        try:
            n=normalized(text)
            e=self.engine
            async with e.lock:
                snapshot=e.snapshot()
                symbol=symbol_in(text,e.settings.allowlist)
                command_form=bool(re.search(r'\b(kapat|ac|al|sat|dene|yap|kapatir misin|acar misin)[.!?]*$',n))
                hypothetical=bool(re.search(r'\b(eger|olursa|oldugunda|duserse|cikarsa|gecerse|ornek|ornegin|varsay|dersem|diyelim|nedir|nasil)\b|ne olur|ne anlama',n))
                mission_request=bool(re.search(r'\b(tara|tarayip|gorev baslat|firsat (ara|bul))\b',n))
                if not hypothetical and mission_request and re.search(r'\d',n):
                    if not supported_mission_request(text):
                        self.answer(id,'İstediğin ek kapsamı yok sayarak görev hazırlamadım. Şu an görevler izleme listesindeki tüm coinleri, Binance ve Bybit spot/vadeli piyasalarını birlikte kapsıyor. Coin, borsa, yön, piyasa türü, özel risk veya koşul filtresi sohbet görevinde desteklenmiyor. Desteklenen istek: “100 USDT ile 2x piyasayı tara”. Süre ve pozisyon sınırını İşlem merkezi ekranından seçebilirsin.','plan');return
                    amounts=re.findall(r'(\d+(?:[.,]\d+)?)\s*(?:usdt|usd|dolar|\$)',n)
                    levs=re.findall(r'\b(\d+)\s*x\b',n)
                    if len(amounts)!=1 or len(levs)>1:
                        self.answer(id,'Görev bütçesini açıkça yaz: “100 USDT ile piyasayı tara”. Kapsamı İşlem merkezi ekranında da seçebilirsin.');return
                    payload=dict(capital=float(amounts[0].replace(',','.')),leverage=int(levs[0]) if levs else min(3,e.settings.leverage),max_positions=min(3,e.settings.max_positions),duration_hours=24)
                    result=self.mission_plan(payload,id)
                    self.answer(id,result['message'],'plan');return
                if not hypothetical and re.search(r'firsat|islem gorev|gorev (durum|sonuc)|hangi coin.*uygun',n):
                    op=e.operations.snapshot();mission=op['mission'];coverage=op['coverage']
                    lines=[f"{op['mode']} · tamamlanan analiz bağlamı {coverage['analyzed']}/{coverage['total']}."]
                    if mission:lines.append(f"Görev {mission['status']}: bütçe {money(mission['capital'])} USDT, kullanılan {money(mission['used_capital'])}, tahmini net {money(mission['net'])} USDT. {mission.get('reason','')}")
                    for row in op['opportunities'][:5]:lines.append(f"{row['symbol']} · {row['venue']} · {row['market']} · {row['side']}: karşılaştırma puanı {row['score']}/100 ({row['status']}); {row['reason']}")
                    if not op['opportunities']:lines.append('Henüz onaylı giriş sinyali yok. İşlem açmak için bir gerekçe uydurulmadı.')
                    lines.append('Karşılaştırma puanı kazanma olasılığı değildir. Bütçeli görev için İşlem merkezi ekranını açabilirsin.')
                    self.answer(id,'\n'.join(lines));return
                if re.fullmatch(r'(lutfen )?(yeni girisleri durdur|botu durdur|islem acmayi durdur|duraklat)[.!]?',n):
                    self.plan(id,'pause','Yeni girişleri durdur','Yeni girişler duracak. Açık sanal pozisyonların stop/hedef takibi devam edecek.')
                    self.answer(id,'Yeni girişleri durdurmak için aşağıdaki planı onayla. Henüz değişiklik yapmadım.','plan');return
                if re.fullmatch(r'(lutfen )?(oturumu surdur|botu baslat|yeni girisleri baslat|islemleri baslat)[.!]?',n):
                    self.plan(id,'resume','Sanal oturumu sürdür','Mevcut sanal bakiye ile otomatik stratejiler çalışacak. Yeni oturum oluşturulmayacak; mevcut risk sınırları geçerli.')
                    self.answer(id,'Mevcut sanal oturumu sürdürmek için planı onayla.','plan');return
                if command_form and not hypothetical and re.search(r'\b(kapat|kapatir misin)\b',n) and ('pozisyon' in n or 'islem' in n):
                    scope=close_scope(text,e.settings.allowlist)
                    if scope is None:
                        self.answer(id,'Kapatma kapsamı belirsiz veya desteklenmeyen bir koşul içeriyor; plan oluşturmadım. Tek coin, tek borsa, spot/vadeli ve long/short filtresi yazabilirsin: “Bybit vadeli BTC long pozisyonunu kapat”. Tümünü kapatmak için “Tüm pozisyonları kapat” yaz. Hariç tutma, çoklu coin ve kâr/zarar koşulları bu komutta desteklenmiyor.','plan');return
                    positions=[p for p in snapshot['positions'] if all(not value or p[key]==value for key,value in scope.items())]
                    if not positions:
                        self.answer(id,'Kapatılacak pozisyon bulunamadı. Coini açıkça yazabilirsin: “BTC pozisyonunu kapat”.');return
                    for p in positions:
                        self.plan(id,'close','Sanal pozisyonu kapat',f"{p['symbol']} · {p['venue']} · {p['market']} · {p['side']}\nŞimdi kapanırsa tahmini net: {money(p['net_if_close'])} USDT. Gerçekleşme anındaki güncel alış/satış kullanılacak.",dict(position_id=p['id']))
                    self.answer(id,'Kapatma planlarını aşağıda hazırladım. Her pozisyon kendi onayıyla, güncel fiyat ve maliyetlerle kapatılacak. Yeni girişler ayrıca durdurulmaz.','plan');return
                if command_form and not hypothetical and ((re.search(r'\b(ac|al|sat|dene|acar misin)\b',n) and re.search(r'\b(long|short|islem|vadeli|spot|pozisyon)\b',n))
                    or re.search(r'\b(islem|pozisyon)\s+yap\b',n)):
                    trade=True
                else:trade=False
                if not trade and re.search(r'\bne\b.*islem.*(yap|ac)|son.*islem|islem.*gecmis|islemlerimi|acik pozisyon|\bne\b.*pozisyon',n):
                    rows=snapshot['closed'][:5]
                    lines=[f"{snapshot['mode']} hesap · {stamp(snapshot['timestamp'])}",f"{len(snapshot['positions'])} açık pozisyon; {snapshot['metrics']['closed_count']} kapanmış işlem."]
                    for p in snapshot['positions'][:12]:lines.append(f"Açık: {p['symbol']} · {p['venue']} · {p['side']} {p['leverage']}x · kapanırsa tahmini net {money(p['net_if_close'])} USDT.")
                    for p in rows:lines.append(f"Kapandı: {p['symbol']} · {p['side']} · net {money(p['net'])} USDT · {p['reason']} · {stamp(p['closed_at'])}.")
                    if not rows:lines.append('Henüz kapanmış işlem yok; örnek sonuç eklemedim.')
                    self.answer(id,'\n'.join(lines));return
                if not trade and ('neden' in n and ('ac' in n or 'bekli' in n)):
                    decisions=sorted([d for d in snapshot['decisions'] if not symbol or d['symbol']==symbol],key=lambda d:d['observed'],reverse=True)[:6]
                    lines=[f"Yeni girişler {'açık' if e.state['running'] else 'duraklatılmış'}. "+(e.state['halt'] or '')]
                    lines.extend(f"{d['symbol']} · {d['venue']} · {d['market']} · {d['strategy']}: {d['message']} ({stamp(d['observed'])})." for d in decisions)
                    if not decisions:lines.append('Henüz tamamlanmış analiz kaydı yok. Mevcut olmayan bir gerekçe uyduramam.')
                    self.answer(id,'\n'.join(lines));return
                if not trade and re.search(r'bakiye|hesab|portfoy|kar.?zarar|ne kadar (kaz|kay|kar|zarar)|risk.*(durum|sinir)',n) and not ('analiz' in n):
                    m=snapshot['metrics'];s=e.settings
                    self.answer(id,f"{snapshot['mode']} hesap · {stamp(snapshot['timestamp'])}\nBakiye: {money(m['equity'])} USDT. Maliyet sonrası net sonuç: {money(m['net'])} USDT.\nAçık pozisyon: {len(snapshot['positions'])}/{s.max_positions}. Açık planlanan risk: {money(m['open_risk'])} USDT (%{money(m['risk_pct'])}).\nHesap düşüşü: %{money(m['drawdown'])}. Toplam açık risk sınırı: %{money(s.total_risk)}. Kaldıraç tavanı: {s.leverage}x.\nGerçek para kullanılmıyor; komisyon/kayma ve tasfiye modeli tahminidir.");return
                if not trade and re.search(r'(son|guncel).*haber|haberleri.*(ozet|goster)|gundem.*(ne|ozet)',n):
                    events=sorted(snapshot['news'],key=lambda x:x.get('published_at',''),reverse=True)[:4]
                    lines=[f"{snapshot['mode']} haber kayıtları · {stamp(time.time())}"]
                    lines.extend(f"{ev['source']} · {ev['published_at']}\n{ev['title']}\n{ev.get('url') or 'Örnek DEMO olayı'}" for ev in events)
                    if not events:lines.append('Henüz doğrulanmış kaynak kaydı yok.')
                    lines.append('Bu kaynak başlıklarıdır; eksiksiz dünya haber akışı veya doğrulanmış piyasa etkisi değildir.')
                    self.answer(id,'\n\n'.join(lines));return
            if trade:
                await self.prepare_trade(id,text,symbol);return
            if symbol and re.search(r'analiz|piyasa|trend|fiyat|grafik',n):
                await self.analyze(id,text,symbol);return
            if not e.settings.local_ai_enabled or e.local_ai.disabled or not e.local_ai.available:
                self.answer(id,'Serbest sohbet için ücretsiz yerel model etkin ve kurulu olmalı. Ayarlar → Ücretsiz yerel AI bölümünü açabilirsin. Hesap, işlem geçmişi ve “Neden işlem açmadın?” soruları model olmadan da çalışır.','unavailable');return
            async with e.ai_cycle_lock:
                if self.closing:return
                async with e.lock:
                    s=e.snapshot()
                    facts=dict(mode=s['mode'],running=s['running'],observed=s['timestamp'],metrics=s['metrics'],
                               risk=dict(leverage=s['settings']['leverage'],total_risk=s['settings']['total_risk']),
                               open_positions=[{k:p[k] for k in ('symbol','venue','market','side','leverage','net_if_close')} for p in s['positions'][:4]],
                               recent_decisions=[{k:d[k] for k in ('symbol','message','observed')} for d in sorted(s['decisions'],key=lambda x:x['observed'],reverse=True)[:4]])
                    context=dict(message=text,facts=facts,knowledge=research_context(),requested_history=history_context(getattr(e,'history_service',None)),
                                 news=[dict(id=x['id'],title=x['title'][:180],source=x['source'],published_at=x['published_at']) for x in s['news'][:3]],
                                 conversation=[dict(role=m['role'],content=m['content'][:300]) for m in self.messages if m['status']=='done'][-4:])
                result=await asyncio.to_thread(e.local_ai.converse,context)
            self.answer(id,result['answer'],'ai',knowledge_ids=result['knowledge_ids'],data_at=facts['observed'],mode=facts['mode'],grounding=result.get('grounding'))
        except asyncio.CancelledError:
            message=next((m for m in self.messages if m['id']==id),None)
            if message:message.update(status='error',content='Yanıt tamamlanmadan uygulama kapandı. Mesajını tekrar gönderebilirsin.');self.save()
            raise
        except Exception:
            message=next((m for m in self.messages if m['id']==id),None)
            if message:message.update(status='error',content='Yanıt tamamlanamadı. Yerel model veya veri bağlantısı hazır olduğunda tekrar deneyebilirsin. Hiçbir işlem uygulanmadı.');self.save()

    async def analyze(self,id,text,symbol):
        e=self.engine;n=normalized(text)
        source=e.mode
        venue='Bybit' if 'bybit' in n else 'Binance'
        market='futures' if 'vadeli' in n or 'futures' in n else 'spot'
        if '6 ay' in n or '1 yil' in n or '12 ay' in n:
            months=6 if '6 ay' in n else 12
            result=await asyncio.to_thread(e.history_service.get,symbol,venue,market,months,'1d',source)
            if e.mode!=source:self.answer(id,'Çalışma modu değişti; eski modun analizi kullanılmadı. Tekrar isteyebilirsin.');return
            s=result['summary'];c=result['coverage']
            self.answer(id,f"{symbol} · {venue} · {market} · {months} ay · {source}\n{c['actual']}/{c['expected']} kapanmış mum; kapsam: {c['status']}.\nFiyat değişimi: {money(s['return_pct'])+'%' if s['return_pct'] is not None else 'veri yok'}. Kapanış bazlı en büyük fiyat düşüşü: {money(s['max_drawdown_pct'])+'%' if s['max_drawdown_pct'] is not None else 'veri yok'}.\nGünlük trend: {dict(up='yükseliş',down='düşüş',mixed='karışık',insufficient='veri yetersiz')[s['daily_context']['trend']]}.\n"+'\n'.join(s['limitations'])+'\nBunlar fiyat ölçümleridir; hesabın getirisi veya al/sat tavsiyesi değildir.','analysis');return
        rows=await asyncio.to_thread(e.candles,symbol,'15m',venue,market,False,source)
        async with e.lock:
            if e.mode!=source:self.answer(id,'Çalışma modu değişti; eski modun analizi kullanılmadı. Tekrar isteyebilirsin.');return
            q=copy.deepcopy(e.quote(venue,symbol,market))
        if not rows or not q:self.answer(id,'Bu piyasa için henüz güncel mum/kotasyon yok. Örnek veriyle boşluğu doldurmadım.');return
        import pandas as pd
        close=pd.Series([r['close'] for r in rows]);delta=close.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
        ema20=float(close.ewm(span=20,adjust=False).mean().iloc[-1]);ema50=float(close.ewm(span=50,adjust=False).mean().iloc[-1]);rsi=float((100-100/(1+gain/loss.clip(lower=1e-12))).iloc[-1])
        trend='yükseliş' if close.iloc[-1]>ema20>ema50 else 'düşüş' if close.iloc[-1]<ema20<ema50 else 'karışık'
        self.answer(id,f"{symbol} · {venue} · {market} · {source}\nSon fiyat: {q['price']:.8g} USDT; fiyat verisinin yaşı {max(0,time.time()-q.get('price_observed',q['observed'])):.1f} sn.\n15 dakikalık {len(rows)} kapanmış mum. Son mum kapanışı: {stamp(rows[-1]['time']+900)}.\nKısa dönem görünüm: {trend}. EMA20: {ema20:.8g}; EMA50: {ema50:.8g}; RSI14: {rsi:.1f}.\nBu göstergeler tek başına giriş veya kazanma olasılığı değildir. 6 aylık / 1 yıllık analiz de isteyebilirsin.",'analysis')

    async def prepare_trade(self,id,text,symbol):
        e=self.engine;n=normalized(text)
        if re.search(r'\bstop\w*|\bhedef\w*|\blimit\w*|\brisk\w*|\bemir\w*|kar al|sonra|kosullu',n):
            self.answer(id,'Özel stop/hedef, limit veya koşullu emir bu sohbet sürümünde desteklenmiyor. İstediğin koşulu yok sayarak işlem hazırlamadım. Desteklenen plan: azami bütçe, coin, yön ve kaldıraç; stop 2×ATR, hedef 2R ve en fazla 4 saat.','plan');return
        amounts=list(re.finditer(r'(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:usdt|dolar|usd|\$)',n))
        leverages=list(re.finditer(r'\b(\d+)\s*x\b',n))
        if (len(amounts)>1 or len(leverages)>1
                or re.search(r'\b(?:degil|haric\w*|disind\w*|yerine|vazgec\w*)\b',n)):
            self.answer(id,'Birden fazla bütçe/kaldıraç veya hariç tutma/düzeltme ifadesi var; ilk değeri seçerek plan hazırlamadım. Tek bütçe, tek kaldıraç ve tek yönle isteğini yeniden yaz.','plan');return
        if re.search(r'\b(?:cross|capraz)\b',n):
            self.answer(id,'Cross/çapraz teminat bu sanal işlem sürümünde desteklenmiyor. İstediğin teminat türünü yok sayarak plan hazırlamadım; vadeli işlemler yalnız isolated/izole teminatla modellenir.','plan');return
        amount=amounts[0] if amounts else None
        leverage=leverages[0] if leverages else None
        side='short' if re.search(r'\bshort\b',n) else 'long' if re.search(r'\blong\b',n) else None
        if (('binance' in n and 'bybit' in n) or (re.search(r'\blong\b',n) and re.search(r'\bshort\b',n))
            or ('spot' in n and ('vadeli' in n or 'futures' in n or (leverage and int(leverage.group(1))>1)))):
            self.answer(id,'Planın borsası, yönü veya piyasa türü birden fazla anlama geliyor. Tek borsa, tek yön ve spot/vadeli seçimini açıkça yaz.','plan');return
        if not symbol or not amount or not side:
            self.answer(id,'Plan için coin, azami teminat/alış bütçesi ve yönü açıkça yaz. Örnek: “BTC 100 USDT bütçeyle 3x vadeli long işlem aç”. Bütçe harcama hedefi değildir; risk sınırları daha küçük pozisyon üretebilir. Henüz işlem yapılmadı.','plan');return
        budget=float(amount.group(1).replace(',','.'));lev=int(leverage.group(1)) if leverage else 1
        market='futures' if 'vadeli' in n or 'futures' in n or lev>1 else 'spot'
        venue='Bybit' if 'bybit' in n else 'Binance'
        async with e.lock:
            if e.mode!='PAPER':self.answer(id,'İşlem planları yalnız gerçek verili Sanal modda hazırlanır. Önce Sanal moda geç.','plan');return
            session=e.state.get('session_id')
            if lev>e.settings.leverage:self.answer(id,f'İstediğin {lev}x, seçili profilin {e.settings.leverage}x tavanını aşıyor. Profilini sohbetten yükseltmedim. Mevcut tavana uygun kaldıraçla yeniden plan isteyebilirsin.','plan');return
        rows=await asyncio.to_thread(e.candles,symbol,'15m',venue,market,False,'PAPER')
        if len(rows)<30:self.answer(id,'ATR stopu için yeterli gerçek kapanmış mum yok; plan oluşturulmadı.','plan');return
        ranges=[max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close'])) for a,b in zip(rows,rows[1:])]
        atr=sum(ranges[:14])/14
        for value in ranges[14:]:atr=(atr*13+value)/14
        price=rows[-1]['close'];distance=atr*2;direction=1 if side=='long' else -1
        if not math.isfinite(distance) or distance<=0 or atr/price>.025:self.answer(id,'Oynaklık/ATR koşulu plan için uygun değil.','plan');return
        sig=Signal(strategy='intraday',symbol=symbol,venue=venue,market=market,side=side,price=price,
                   stop=price-direction*distance,target=price+direction*distance*2,method='manual',
                   candle_time=rows[-1]['time'],reason='Sohbette kullanıcının seçtiği yön; onaylı otomatik strateji sinyali değildir.')
        async with e.lock:
            if e.mode!='PAPER' or e.state.get('session_id')!=session:self.answer(id,'Hesap/mod değişti; plan oluşturulmadı.','plan');return
            preview=e.open_signal(sig,budget_limit=budget,requested_leverage=lev,origin='chat',preview=True)
            if not preview['ok']:self.answer(id,'Plan risk kontrolünden geçmedi: '+preview['message'],'plan');return
            summary=(f"{symbol} · {venue} · {'Vadeli' if market=='futures' else 'Spot'} · {side.upper()} · {lev}x\n"
                     f"Azami bütçe {money(budget)} USDT; tahmini kullanılan tutar {money(preview['capital_required'])} USDT.\n"
                     f"Tutar {money(preview['notional'])} USDT; miktar {preview['quantity']:.8g}. Giriş ≈ {preview['entry']:.8g}.\n"
                     f"Stop {preview['stop']:.8g}; hedef {preview['target']:.8g}; maliyet dahil planlanan kayıp ≈ {money(preview['planned_risk'])} USDT.\n"
                     'Kullanıcının seçtiği manuel yön; otomatik sinyal değildir. Çıkış: stop/hedef veya en fazla 4 saat. '
                     +('Adaptif çıkış: uygun büyüklükte +1R’de yarısı kapanır; kalanı maliyetli başabaş ve takip stopuyla izlenir. ' if e.settings.exit_policy=='adaptive' else 'Sabit çıkış politikası seçili. ')
                     +'Fonlama ve fiyat boşluğu ek kayıp yaratabilir.')
            self.plan(id,'trade','Sanal işlem planını onayla',summary,dict(signal=sig.model_dump(),budget=budget,leverage=lev,preview=preview))
            self.answer(id,'Sanal işlem planı hazır. Onayda fiyat, bütçe ve bütün risk kontrolleri yeniden yapılacak. Plan 2 dakika geçerli; fiyat %0,3 üzerinde değişirse yeni plan gerekir.','plan')

    async def execute(self,id):
        e=self.engine
        async with e.lock:
            receipt=e.store.get('chat_receipt:'+id)
            if receipt:return receipt
            if e.closing:return dict(ok=False,message='Motor kapanıyor; yeni talimat uygulanamaz.')
            p=next((p for p in self.plans if p['id']==id),None)
            if not p or p['status']!='proposed':return dict(ok=False,message='Onaylanabilir plan bulunamadı.')
            if p['expires_at']<time.time() or p['mode']!=e.mode or p['session_id']!=e.state.get('session_id'):
                p['status']='expired';self.save();return dict(ok=False,message='Planın süresi doldu veya hesap/mod değişti. Yeni plan iste.')
            before=copy.deepcopy(e.state);plans_before=copy.deepcopy(self.plans);messages_before=copy.deepcopy(self.messages)
            try:
                with e.store.atomic():
                    if e.mode!='PAPER':result=dict(ok=False,message='Sohbet komutları yalnız Sanal modda uygulanır.')
                    elif p['kind']=='mission':result=e.operations.activate(p['payload'])
                    elif p['kind']=='trade':
                        payload=p['payload'];sig=Signal(**payload['signal'])
                        current=e.open_signal(sig,budget_limit=payload['budget'],requested_leverage=payload['leverage'],origin='chat',preview=True)
                        old=payload['preview']
                        if not current['ok']:result=current
                        elif abs(current['entry']/old['entry']-1)>.003 or current['planned_risk']>old['planned_risk']*1.02+1e-7:
                            result=dict(ok=False,message='Fiyat/risk plan sınırından değişti; yeni plan iste.')
                        else:result=e.open_signal(sig,budget_limit=payload['budget'],requested_leverage=payload['leverage'],origin='chat')
                    elif p['kind']=='close':result=e.close_position(p['payload']['position_id'],'Sohbette kullanıcı onayladı')
                    elif p['kind'] in ('pause','resume'):
                        if p['kind']=='resume' and e.state['halt']:result=dict(ok=False,message=e.state['halt'])
                        else:
                            e.state['running']=p['kind']=='resume'
                            if e.state['running']:e.state['started_at']=e.state['started_at'] or time.time()
                            e.audit('chat_command','Sohbette kullanıcı onayladı: '+p['kind'])
                            if e.state['running']:e.scan_wake.set()
                            e.save();result=dict(ok=True,message='Yeni girişler durduruldu; stop/hedef takibi devam ediyor.' if p['kind']=='pause' else 'Mevcut sanal oturum sürdürüldü.')
                    else:result=dict(ok=False,message='Geçersiz plan.')
                    p['status']='executed' if result['ok'] else 'rejected'
                    e.store.set('chat_receipt:'+id,result)
                    self.messages.append(dict(id=uuid.uuid4().hex,role='assistant',content=result['message'],created_at=time.time(),status='done',kind='result'))
                    self.save()
                return result
            except Exception:
                e.states[e.mode]=before;self.plans=plans_before;self.messages=messages_before
                return dict(ok=False,message='İşlem kaydı tamamlanamadı; durum geri alındı.')
