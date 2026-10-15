import {useCallback,useEffect,useRef,useState} from 'react';
import {ArrowRight,CheckCircle2,Clock3,Compass,LoaderCircle,MessageSquare,Pause,ShieldCheck,Target,TriangleAlert} from 'lucide-react';
import type {Row,Snapshot} from './types';
import './operations.css';

type Operations={mode:string;session_id:string;timestamp:number;mission:Row|null;coverage:{analyzed:number;total:number;updated_at:number};opportunities:Row[];decisions:Row[]};
const num=(value:number,d=2)=>new Intl.NumberFormat('tr-TR',{minimumFractionDigits:d,maximumFractionDigits:d}).format(Number.isFinite(value)?value:0);
const signed=(value:number)=>(value>=0?'+':'−')+num(Math.abs(value));
const at=(value:number)=>value?new Date(value*1000).toLocaleString('tr-TR',{timeZone:'Europe/Istanbul',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}):'Henüz yok';
const statusNames:Row={active:'Yeni girişlere açık',paused:'Yeni girişler duraklatıldı',expired:'Görev süresi tamamlandı',completed:'Görev tamamlandı',eligible:'Değerlendirilebilir',blocked:'Risk kontrolü engelledi',opened:'Pozisyon açıldı',stale:'Veri yenilenmeli',rejected:'Giriş yapılmadı',accepted:'Kabul edildi'};
const methodNames:Row={breakout:'Kırılım',momentum:'Momentum',pullback:'Geri çekilme',reversion:'Ortalamaya dönüş',squeeze:'Sıkışma'};

export function OperationsPanel({data,simple,notify,openChat}:{data:Snapshot;simple:boolean;notify:(text:string,ok?:boolean)=>void;openChat:()=>void}){
 const [state,setState]=useState<Operations|null>(null);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState('');
 const [action,setAction]=useState<Row|null>(null);
 const [capital,setCapital]=useState('100');
 const [leverage,setLeverage]=useState(String(Math.min(3,data.settings.leverage||1)));
 const [maximum,setMaximum]=useState(String(Math.min(3,data.settings.max_positions||1)));
 const [hours,setHours]=useState('24');
 const alive=useRef(false),mutation=useRef(false),generation=useRef(0);
 const refresh=useCallback(async()=>{const epoch=generation.current;try{const next=await window.terminal.request<Operations>('/operations');if(alive.current&&epoch===generation.current){setState(next);setError('');}}catch{if(alive.current&&epoch===generation.current)setError('İşlem merkezi bağlantısı kurulamadı. Yeniden deneniyor.');}},[]);
 useEffect(()=>{alive.current=true;let timer:number|undefined;let cancelled=false;generation.current++;setState(null);setAction(null);setBusy('');async function poll(){await refresh();if(!cancelled)timer=window.setTimeout(poll,2000);}poll();return()=>{cancelled=true;alive.current=false;generation.current++;window.clearTimeout(timer);};},[refresh,data.mode,data.session.id]);
 const mission=state?.mission;
 const current=state?.mode===data.mode&&state?.session_id===data.session.id;
 const paper=data.mode==='PAPER';
 const limits=data.settings;
 const valid=Number(capital)>=10&&Number.isFinite(Number(capital))&&Number.isInteger(Number(leverage))&&Number(leverage)>=1&&Number(leverage)<=limits.leverage&&Number.isInteger(Number(maximum))&&Number(maximum)>=1&&Number(maximum)<=limits.max_positions&&Number.isInteger(Number(hours))&&Number(hours)>=1&&Number(hours)<=72;
 async function mutate(kind:'plan'|'confirm'|'pause'){
  if(mutation.current)return;mutation.current=true;setBusy(kind);setError('');
  const epoch=generation.current;
  try{
   const result=await window.terminal.request(kind==='confirm'?'/chat/action':`/operations/${kind}`,'POST',kind==='plan'?{capital:Number(capital),leverage:Number(leverage),max_positions:Number(maximum),duration_hours:Number(hours)}:kind==='confirm'?{id:action?.id}:{});
   if(!alive.current||epoch!==generation.current)return;
   if(result.ok===false)throw new Error(result.message||'Talimat uygulanamadı.');
   if(kind==='plan')setAction(result.action||null);else{setAction(null);notify(result.message||'Görev güncellendi.');}
   await refresh();
  }catch(e){if(alive.current&&epoch===generation.current)setError(e instanceof Error?e.message:'Talimat uygulanamadı.');}
  finally{mutation.current=false;if(alive.current&&epoch===generation.current)setBusy('');}
 }
 const opportunities=current?state?.opportunities||[]:[];
 const decisions=current?state?.decisions||[]:[];
 const expired=!!action?.expires_at&&(state?.timestamp||Date.now()/1000)>=action.expires_at;
 return <section className="operations-page" data-testid="operations-panel">
  <div className="operations-heading"><div><div className="eyebrow">KAPSAMI BELLİ, SONUCU TAKİP EDİLEN</div><h1>İşlem merkezi</h1><p>Bütçeni belirle. Bot, uygun sinyalleri karşılaştırsın ve görev sınırlarında değerlendirsin.</p></div><button className="button secondary" onClick={openChat}><MessageSquare size={15}/>Bota sor<ArrowRight size={13}/></button></div>
  {!paper&&<div className="notice"><TriangleAlert size={17}/><span>Görevler gerçek piyasa verili Sanal modda çalışır. Çalışma modunu Sanal olarak değiştirerek mevcut hesabınla devam edebilirsin.</span></div>}
  {error&&<div className="operations-error" role="alert"><TriangleAlert size={16}/>{error}</div>}
  <div className="operations-top-grid">
   <section className="panel operations-form"><div className="operations-section-heading"><span className="operations-icon"><Compass size={21}/></span><div><h2>Sanal işlem görevi</h2><p>Tek onayla sınırları belli bir çalışma başlat.</p></div></div>
    <form onSubmit={e=>{e.preventDefault();if(valid&&paper&&!busy)mutate('plan');}}>
     <div className="operations-fields">
      <label>Görev bütçesi <span>USDT</span><input aria-label="Görev bütçesi USDT" type="number" min="10" step="0.01" value={capital} onChange={e=>{setCapital(e.target.value);setAction(null);}}/></label>
      <label>Azami kaldıraç <span>×{limits.leverage} hesap sınırı</span><input aria-label="Görev azami kaldıraç" type="number" min="1" max={limits.leverage} step="1" value={leverage} onChange={e=>{setLeverage(e.target.value);setAction(null);}}/></label>
      <label>Eşzamanlı pozisyon <span>En fazla {limits.max_positions}</span><input aria-label="Görev azami pozisyon" type="number" min="1" max={limits.max_positions} step="1" value={maximum} onChange={e=>{setMaximum(e.target.value);setAction(null);}}/></label>
      <label>Yeni giriş süresi <span>Saat · en fazla 72</span><input aria-label="Görev süresi saat" type="number" min="1" max="72" step="1" value={hours} onChange={e=>{setHours(e.target.value);setAction(null);}}/></label>
     </div>
     <p className="operations-form-note"><ShieldCheck size={15}/>Bütçe harcama hedefi değildir. Hesabın ortak risk sınırları uygulanır; uygun sinyal yoksa işlem açılmaz. Süre sonunda mevcut pozisyonların koruyucu çıkışları sürer.</p>
     <button className="button primary" type="submit" disabled={!paper||!valid||!!busy||!current}>{busy==='plan'?<LoaderCircle size={15} className="spin"/>:<Target size={15}/>}Görev planını gör</button>
    </form>
    {action&&<div className="operations-approval" data-testid="mission-approval" data-action-id={action.id}><strong>Onayından sonra başlayacak</strong>{(Array.isArray(action.summary)?action.summary:String(action.summary||'').split('\n')).map((line:string,i:number)=><p key={i}>{line}</p>)}<small>Onay süresi: {at(action.expires_at)}</small><div className="button-row"><button className="button primary" disabled={!!busy||expired||!paper||!current} onClick={()=>mutate('confirm')}>{busy==='confirm'?<LoaderCircle size={14} className="spin"/>:<CheckCircle2 size={14}/>} {expired?'Planın süresi doldu':'Bu görevi onayla'}</button><button className="button subtle" disabled={!!busy} onClick={()=>setAction(null)}>Vazgeç</button></div></div>}
   </section>
   <section className="panel operations-mission" data-testid="mission-status"><div className="operations-section-heading"><span className="operations-icon"><ShieldCheck size={21}/></span><div><h2>Görev durumu</h2><p>Bu göreve ait bütçe ve sonuçlar.</p></div></div>
    {!current?<div className="operations-empty"><LoaderCircle className="spin" size={22}/><strong>Görev kayıtları hazırlanıyor.</strong></div>:!mission?<div className="operations-empty"><Compass size={28}/><strong>Henüz işlem görevi yok.</strong><p>Önce planını incele, ardından onayla. Mevcut hesap ve işlemler korunur.</p></div>:<><div className={'operations-mission-state '+mission.status}><i className="status-dot"/>{mission.status==='active'&&!data.running?'Görev onaylı · hesap girişleri duraklatıldı':statusNames[mission.status]||mission.status}</div><div className="operations-metrics"><div><span>Görev bütçesi</span><strong>{num(mission.capital)} <small>USDT</small></strong></div><div><span>Uygun boş bütçe</span><strong>{num(mission.available_capital)} <small>USDT</small></strong></div><div><span>Açık risk</span><strong>{num(mission.open_risk)} <small>USDT</small></strong></div><div><span>Görev neti ≈</span><strong className={mission.net>=0?'positive-text':'negative-text'}>{signed(mission.net)} <small>USDT</small></strong></div></div><div className="operations-mission-meta"><span>{Array.isArray(mission.positions)?mission.positions.length:mission.positions||0} / {mission.effective_max_positions??mission.max_positions} açık pozisyon · en fazla ×{mission.effective_leverage??mission.leverage}</span><span><Clock3 size={13}/>Yeni giriş sonu {at(mission.expires_at)}</span>{mission.reason&&<p>{mission.reason}</p>}</div>{mission.status==='active'&&<button className="button secondary" disabled={!!busy} onClick={()=>mutate('pause')}><Pause size={14}/>Görevin yeni girişlerini durdur</button>}<p className="operations-disclosure">Görev neti, gerçekleşmiş sonuçlarla açık pozisyonların maliyetli tahmini toplamıdır. Açık pozisyonların sonucu kapanışa kadar değişir. {mission.valuation_fresh===false&&' Alış/satış verisi eski; net değer son bilinen kotasyonla tahmin ediliyor.'}</p></>}
   </section>
  </div>
  <section className="panel operations-opportunities"><div className="operations-list-heading"><div><h2>Fırsat karşılaştırması</h2><p>Karşılaştırma puanı, kâr olasılığı değildir. Her giriş güncel risk kontrolünden yeniden geçer.</p></div><span className="badge blue">{current?state?.coverage?.analyzed||0:0} / {current?state?.coverage?.total||0:0} analiz</span></div>
   {!opportunities.length?<div className="operations-empty"><Target size={25}/><strong>Karşılaştırılacak güncel sinyal bekleniyor.</strong><p>Tarama tamamlandıkça uygun sinyaller ve girişe izin verilmeyen durumlar burada görünür.</p></div>:<div className="operations-candidates">{opportunities.slice(0,simple?6:20).map((item,i)=><article className="operations-candidate" key={item.id}><div className="operations-candidate-head"><span className="operations-rank">{i+1}</span><div><strong>{item.symbol.replace('USDT','')} <span className="muted">/ USDT</span></strong><small>{item.venue} · {item.market==='spot'?'Spot':'Vadeli'} · {item.strategy==='intraday'?'15dk':'4s'} · {item.side==='long'?'LONG':'SHORT'}</small></div><div className="operations-score"><strong>{Number.isFinite(item.score)?num(item.score,0):'—'}</strong><small>{item.score_label||'Karşılaştırma puanı'}</small></div></div><div className="operations-candidate-detail"><span className={'badge '+(item.status==='opened'?'positive':item.status==='eligible'?'blue':'warning')}>{statusNames[item.status]||item.status}</span><span>{methodNames[item.method]||item.method}</span><span>{Math.max(0,Math.floor((state?.timestamp||Date.now()/1000)-item.observed))} sn önce</span></div><p>{item.reason}</p>{(item.entry||item.planned_risk)&&<div className="operations-candidate-values">{item.entry&&<span>Giriş ≈ <strong>{num(item.entry,item.entry<1?6:2)}</strong></span>}{item.planned_risk!==undefined&&<span>Planlanan risk <strong>{num(item.planned_risk)} USDT</strong></span>}{item.capital_required!==undefined&&<span>Gerekli bütçe <strong>{num(item.capital_required)} USDT</strong></span>}</div>}{!simple&&<div className="operations-candidate-values"><span>Kapanmış mum {at(item.candle_time)}</span><span>Sinyal sonu {at(item.expires_at)}</span>{item.stop&&<span>Stop {num(item.stop,item.stop<1?6:2)}</span>}{item.target&&<span>Hedef {num(item.target,item.target<1?6:2)}</span>}</div>}</article>)}</div>}
   <div className="operations-coverage">Son tarama kaydı {at(current?state?.coverage?.updated_at||0:0)} · Anlık fiyat bağlantısı, bütün strateji analizlerinin tamamlandığı anlamına gelmez.</div>
  </section>
  <section className="panel operations-journal"><div className="operations-list-heading"><div><h2>Karar günlüğü</h2><p>Girişler ve ret gerekçeleri yeniden açılışta korunur.</p></div><span className="badge">{decisions.length} kayıt</span></div>{!decisions.length?<p className="operations-journal-empty">Görev ve sinyal kararları henüz kaydedilmedi.</p>:<div className="operations-journal-list">{decisions.slice(0,simple?8:30).map(item=><article key={item.id}><time>{at(item.time)}</time><div><strong>{item.symbol||'Görev'} {item.venue&&<span>{item.venue} · {item.market==='spot'?'Spot':'Vadeli'}</span>}</strong><p>{item.reason}</p></div><span className={'badge '+(item.status==='opened'||item.status==='active'?'positive':'neutral')}>{statusNames[item.status]||item.status}</span></article>)}</div>}</section>
 </section>;
}
