from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from multiprocessing import get_context
from typing import Literal

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from engine.core import Engine
from engine.market import Exchange
from engine.models import RiskSettings
from engine.research import run_job
from engine.agents import run_cycle
from engine.history import HistoryService
from engine.chat import ChatService
from engine.state_transaction import state_transaction


class Command(BaseModel):
    kind: str
    payload: dict = Field(default_factory=dict)


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra='forbid',allow_inf_nan=False)
    kind: Literal['backtest','ml'] = 'backtest'
    strategy: Literal['intraday','swing'] = 'intraday'
    symbol: str = Field(default='BTCUSDT',pattern=r'^[A-Z0-9]{5,20}$')
    venue: Literal['Binance','Bybit'] = 'Binance'
    market: Literal['spot','futures'] = 'spot'
    source: Literal['DEMO','PUBLIC'] = 'DEMO'
    months: int = Field(default=36,ge=7,le=36)
    fee_bps: float = Field(default=10,ge=0,le=100)
    slippage_bps: float = Field(default=3,ge=0,le=100)


class CredentialRequest(BaseModel):
    venue: Literal['Binance','Bybit']
    key: str = Field(min_length=8,max_length=512)
    secret: str = Field(min_length=8,max_length=512)
    testnet: bool = False


class ChatRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message:str=Field(min_length=1,max_length=2000)


class ChatActionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(pattern=r'^[a-f0-9]{32}$')


class MissionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    capital:float=Field(ge=10,le=10000000)
    leverage:int=Field(ge=1,le=5,strict=True)
    max_positions:int=Field(ge=1,le=12,strict=True)
    duration_hours:int=Field(ge=1,le=72,strict=True)


def create_app(data_dir,token):
    engine=Engine(data_dir)
    engine.history_service=HistoryService(engine.store.path / 'history')
    chat=ChatService(engine)
    pool=None
    active_jobs=set()

    @asynccontextmanager
    async def lifespan(app):
        await engine.start()
        yield
        await chat.stop()
        for task in active_jobs: task.cancel()
        if active_jobs: await asyncio.gather(*active_jobs,return_exceptions=True)
        await engine.stop()
        if pool:
            workers=list((getattr(pool,'_processes',None) or {}).values())
            pool.shutdown(wait=False,cancel_futures=True)
            for worker in workers:
                if worker.is_alive(): worker.terminate()
                worker.join(timeout=2)

    app=FastAPI(title='Kripto Terminali yerel motor',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.engine=engine
    app.state.chat=chat

    @app.middleware('http')
    async def authorize(request:Request,call_next):
        supplied=request.headers.get('authorization','')
        if not hmac.compare_digest(supplied.encode('utf-8'),('Bearer '+token).encode('utf-8')):
            return JSONResponse({'detail':'Yerel motor kimlik doğrulaması gerekli.'},status_code=401)
        if request.headers.get('origin') not in (None,'null'):
            return JSONResponse({'detail':'Tarayıcı kökeni kabul edilmedi.'},status_code=403)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        return response

    @app.get('/health')
    async def health(): return dict(ok=True,version='0.8.0')

    @app.get('/chat')
    async def chat_messages():
        async with engine.lock:return chat.snapshot()

    @app.get('/operations')
    async def operations_snapshot():
        async with engine.lock:return engine.operations.snapshot()

    @app.post('/operations/plan')
    async def operations_plan(body:MissionRequest):
        async with engine.lock:return chat.mission_plan(body.model_dump())

    @app.post('/operations/pause')
    async def operations_pause():
        async with engine.lock:
            before=__import__('copy').deepcopy(engine.state)
            try:
                with engine.store.atomic():return engine.operations.pause()
            except Exception:
                engine.states[engine.mode]=before
                return dict(ok=False,message='Görev kaydı tamamlanamadı; değişiklik geri alındı.')

    @app.post('/chat')
    async def chat_message(body:ChatRequest):
        async with engine.lock:return chat.submit(body.message)

    @app.post('/chat/action')
    async def chat_action(body:ChatActionRequest):
        return await chat.execute(body.id)

    @app.post('/local-ai-refresh')
    async def local_ai_refresh():
        if not engine.settings.local_ai_enabled or not engine.local_ai.available or engine.local_ai.disabled:
            return dict(ok=False,message='Yerel model kurulu veya etkin değil.')
        if engine.ai_cycle_lock.locked():return dict(ok=False,message='Yerel AI zaten çalışıyor; sonucu bekleyin.')
        if engine.mode!='PAPER':return dict(ok=False,message='Gerçek haber araştırması için Sanal moda geçin; motorun işlem açması gerekmez.')
        task=asyncio.create_task(run_cycle(engine,allow_paused=True))
        engine.tasks.append(task)
        def finished(value):
            if value in engine.tasks:engine.tasks.remove(value)
            if not value.cancelled() and value.exception():
                engine.local_ai.status='error';engine.local_ai.message='Yerel AI yanıtı doğrulanamadı; uygulanmadı.'
        task.add_done_callback(finished)
        return dict(ok=True,message='Yerel haber ve araştırma analizi başlatıldı.')

    @app.post('/local-ai-install')
    async def local_ai_install():
        if engine.local_ai.available:return dict(ok=True,message='Yerel model zaten kurulu.')
        if engine.local_ai.installing:return dict(ok=False,message='İndirme zaten sürüyor.')
        from engine.local_ai_setup import install
        engine.local_ai.installing=True
        task=asyncio.create_task(asyncio.to_thread(install,engine.local_ai))
        engine.tasks.append(task)
        return dict(ok=True,message='Yaklaşık 2,5 GB ücretsiz model indirmesi başlatıldı.')

    @app.post('/shutdown')
    async def shutdown():
        engine.state['running']=False
        engine.save()
        callback=getattr(app.state,'shutdown',None)
        if callback: callback()
        return dict(ok=True)

    @app.get('/snapshot')
    async def snapshot():
        async with engine.lock: return engine.snapshot()

    @app.get('/quote')
    async def quote(symbol:str='BTCUSDT',venue:str='Binance',market:str='spot'):
        if symbol not in engine.settings.allowlist or venue not in ('Binance','Bybit') or market not in ('spot','futures'):
            raise HTTPException(400,'Geçersiz piyasa.')
        async with engine.lock:
            q=engine.quote(venue,symbol,market)
            return dict(quote=dict(q) if q and q.get('price',0)>0 else None,mode=engine.mode,timestamp=time.time())

    @app.post('/command')
    async def command(body:Command): return await engine.command(body.kind,body.payload)

    @app.get('/candles')
    async def candles(symbol:str='BTCUSDT',interval:str='15m',venue:str='Binance',market:str='spot'):
        if symbol not in engine.settings.allowlist or interval not in ('15m','1h','4h','1d') or venue not in ('Binance','Bybit') or market not in ('spot','futures'):
            raise HTTPException(400,'Geçersiz piyasa veya zaman dilimi.')
        mode=engine.mode
        try:
            rows=await asyncio.to_thread(engine.candles,symbol,interval,venue,market,False,mode)
            return dict(rows=rows,source=mode,stale=False)
        except Exception:
            return dict(rows=[],source=mode,stale=True,error='Piyasa verisine erişilemiyor; örnek veriye dönüş yapılmadı.')

    @app.get('/history')
    async def history(symbol:str='BTCUSDT',venue:str='Binance',market:str='spot',months:int=6,interval:str='1d'):
        if symbol not in engine.settings.allowlist or venue not in ('Binance','Bybit') or market not in ('spot','futures') or months not in (6,12) or interval not in ('4h','1d'):
            raise HTTPException(400,'Geçersiz piyasa veya uzun dönem aralığı.')
        source='DEMO' if engine.mode=='DEMO' else 'PAPER'
        return await asyncio.to_thread(engine.history_service.get,symbol,venue,market,months,interval,source)

    @app.post('/settings')
    async def settings(body:RiskSettings):
        if not body.auto_universe and len(body.allowlist)>60:
            raise HTTPException(400,'Elle seçilen coin listesi en fazla 60 parite olabilir.')
        if any(not re.fullmatch('[A-Z0-9]{5,20}',s) for s in body.allowlist):
            raise HTTPException(400,'Coin sembolleri büyük harfli USDT pariteleri olmalıdır.')
        if any(not s.endswith('USDT') for s in body.allowlist): raise HTTPException(400,'İlk sürüm yalnız USDT paritelerini destekler.')
        if body.ai_enabled and (not body.ai_model or not body.ai_daily_budget or not body.ai_monthly_budget or not body.ai_input_price or not body.ai_output_price):
            raise HTTPException(400,'AI için model, günlük/aylık bütçe ve doğrulanmış token fiyatları zorunlu.')
        async with engine.lock:
            if body.auto_universe and engine.universe.catalogs:
                discovered=engine.universe.selection(engine)
                if discovered:
                    body=RiskSettings(**{**body.model_dump(),'allowlist':discovered})
            active_symbols={p['symbol'] for state in engine.states.values() for p in state['positions']}
            if not active_symbols.issubset(set(body.allowlist)):
                raise HTTPException(400,'Açık pozisyonu olan coin izleme listesinden çıkarılamaz. Önce pozisyonu kapatın.')
            try:
                previous_auto=engine.settings.auto_universe
                with state_transaction(engine):
                    engine.settings=body
                    allowed=set(body.allowlist)
                    for state in engine.states.values():
                        if not state.get('sample'):
                            state['markets']=[q for q in state['markets'] if q['symbol'] in allowed]
                            for name in ('decisions','learning','regimes'):
                                state[name]={k:v for k,v in state.get(name,{}).items() if len(k.split(':'))>1 and k.split(':')[1] in allowed}
                    engine.store.set('settings',body.model_dump())
                    engine.audit('settings','Risk ve uygulama ayarları güncellendi; yeni bakiye sıfırlamada uygulanır.')
                    engine.save()
                if body.auto_universe and not previous_auto:
                    engine.universe.refresh_requested=True
            except Exception:
                return dict(ok=False,message='Ayarlar kaydedilemedi; hesap ve ayarlar önceki durumuna alındı.')
        return dict(ok=True,message='Ayarlar kaydedildi.')

    @app.post('/universe-refresh')
    async def universe_refresh():
        if engine.closing:return dict(ok=False,message='Motor kapanıyor.')
        if not engine.settings.auto_universe:return dict(ok=False,message='Önce otomatik coin havuzunu etkinleştirin.')
        engine.universe.refresh_requested=True
        return dict(ok=True,message='Borsa listeleri sıradaki veri turunda yenilenecek; hesap sıfırlanmaz.')

    @app.post('/credentials')
    async def credentials(body:CredentialRequest):
        engine.credentials[body.venue]=Exchange(body.venue,body.key,body.secret,body.testnet)
        engine.connections[body.venue].update(status='stored',authenticated=False,testnet=body.testnet)
        return dict(ok=True,message='Anahtar korumalı depodan motora aktarıldı; emir yetkisi açılmadı.')

    @app.post('/connect')
    async def connect(body:dict):
        venue=body.get('venue')
        if venue not in ('Binance','Bybit'): raise HTTPException(400,'Geçersiz borsa.')
        exchange=engine.credentials.get(venue,Exchange(venue))
        try:
            quote,instruments=await asyncio.gather(asyncio.to_thread(exchange.quote,'BTCUSDT','spot'),asyncio.to_thread(exchange.instruments,'BTCUSDT','spot'))
            authenticated=False
            if exchange.key:
                await asyncio.to_thread(exchange.account)
                authenticated=True
            engine.connections[venue].update(status='connected',authenticated=authenticated,observed=time.time(),
                                             testnet=exchange.testnet,price=quote['price'],symbol=instruments.get('symbol'))
            return dict(ok=True,message='Hesap bağlantısı doğrulandı; emir gönderimi kilitli.' if authenticated else 'Halka açık veri bağlantısı doğrulandı.')
        except Exception:
            engine.connections[venue].update(status='error',authenticated=False)
            return dict(ok=False,message='Bağlantı doğrulanamadı. Ağ, bölgesel erişim, API izinleri ve saat ayarını kontrol edin.')

    @app.post('/secrets')
    async def secrets(body:dict):
        # Only the Electron main process calls this authenticated local endpoint.
        if body.get('kind')=='telegram': engine.telegram=str(body.get('value',''))
        elif body.get('kind')=='ai': engine.ai_key=str(body.get('value',''))
        else: raise HTTPException(400,'Geçersiz gizli bilgi türü.')
        return dict(ok=True)

    @app.post('/telegram-test')
    async def telegram_test():
        ok=await engine.notify('Kripto Terminali bağlantı testi · Gerçek işlem yapılmadı.')
        return dict(ok=ok,message='Test bildirimi gönderildi.' if ok else 'Token, sohbet kimliği ve ağ erişimini kontrol edin.')

    @app.post('/jobs')
    async def jobs(body:BacktestRequest):
        nonlocal pool
        if any(j['status']=='running' for j in engine.jobs): return dict(ok=False,message='Önce mevcut araştırma işinin tamamlanmasını bekleyin.')
        if body.symbol not in engine.settings.allowlist: raise HTTPException(400,'Coin izin listesinde değil.')
        if pool is None: pool=ProcessPoolExecutor(max_workers=1,mp_context=get_context('spawn'))
        id=uuid.uuid4().hex
        job=dict(id=id,kind=body.kind,status='running',created_at=time.time(),message='Veri hazırlanıyor; çalışma ayrı süreçte yürütülüyor.')
        engine.jobs.insert(0,job)
        async def execute():
            try:
                loop=asyncio.get_running_loop()
                result=await loop.run_in_executor(pool,run_job,body.kind,body.model_dump(),str(engine.store.path))
                result.pop('training_trades',None)
                async with engine.lock:
                    engine.store.report(id,result)
                    engine.reports.insert(0,dict(id=id,**result))
                    job.update(status='done',message='Araştırma raporu hazır.')
                    engine.audit('research','Araştırma tamamlandı.',dict(id=id,kind=body.kind,source=body.source))
            except asyncio.CancelledError:
                job.update(status='cancelled',message='Uygulama kapanırken araştırma durduruldu.')
            except Exception as e:
                # Errors can originate from network URLs: never surface credentials/requests.
                message=str(e) if isinstance(e,ValueError) else 'Araştırma tamamlanamadı; veri veya bağımlılık hatası.'
                job.update(status='error',message=message[:240],error_type=type(e).__name__)
        task=asyncio.create_task(execute())
        active_jobs.add(task)
        task.add_done_callback(active_jobs.discard)
        return dict(ok=True,message='Araştırma başlatıldı.',id=id)

    @app.get('/report/{id}')
    async def report(id:str):
        item=next((r for r in engine.reports if r['id']==id),None)
        if not item: raise HTTPException(404,'Rapor bulunamadı.')
        return {**item,'needs_retest':item.get('execution_model')!='bar-causal-v2'}

    @app.post('/news-refresh')
    async def news_refresh():
        from engine.news import collect_news
        events,sources=await asyncio.to_thread(collect_news,engine.news)
        async with engine.lock:
            engine.news,engine.news_sources=events,sources
            engine.store.set('news',events)
            engine.store.set('news_sources',sources)
        return dict(ok=True,message='Kaynaklar kontrol edildi; erişilemeyen kaynaklar ayrı gösterilir.')

    @app.post('/research-proposal')
    async def research_proposal(body:dict):
        if not engine.settings.ai_enabled or not engine.ai_key:
            return dict(ok=False,message='AI kapalı. Model, korumalı API anahtarı ve bütçe girilmelidir.')
        # This version intentionally offers no model-to-trading tool authority.
        # A bounded structured-output provider is implemented in a separate adapter.
        from engine.research_provider import propose
        try:
            result=await propose(engine,str(body.get('prompt',''))[:2000])
            return dict(ok=True,message='Araştırma adayı oluşturuldu; canlıya alınmadı.',proposal=result)
        except ValueError as e:
            return dict(ok=False,message=str(e))
        except Exception:
            return dict(ok=False,message='AI yanıtı alınamadı veya doğrulanamadı; canlı ayarlar değişmedi.')

    return app
