import {useState} from 'react';
import {BrainCircuit,ChevronLeft,ChevronRight,GitCompareArrows,ShieldCheck,TrendingUp} from 'lucide-react';
import type {Row,Snapshot} from './types';

const n=(v:number,d=1)=>new Intl.NumberFormat('tr-TR',{minimumFractionDigits:d,maximumFractionDigits:d}).format(v||0);
const method:Record<string,string>={breakout:'Kanal kırılımı',momentum:'Momentum',pullback:'Trend içi geri çekilme',reversion:'Ortalamaya dönüş',squeeze:'Sıkışma kırılımı'};
const regimes:Record<string,string>={uptrend:'Yükseliş trendi',downtrend:'Düşüş trendi',range:'Yatay piyasa',volatile:'Yüksek oynaklık',unavailable:'Veri bekleniyor'};

export function AdaptiveLearning({data}:{data:Snapshot}){
 const [expanded,setExpanded]=useState(false);
 const [page,setPage]=useState(0);
 const [families,setFamilies]=useState(false);
 const learned=(data.learning||[]).filter(m=>m.schema===3&&!!m.version);
 const preparing=(data.learning||[]).filter(m=>m.schema===3&&!m.version).length;
 const ml=learned.filter(m=>m.status==='active').length;
 const pending=learned.filter(m=>m.pending_version).length;
 const feedback=learned.reduce((total,m)=>total+(m.feedback_count||0),0);
 const decisions=(data.decisions||[]).slice().sort((a,b)=>b.observed-a.observed);
 const models=new Map(learned.map(m=>[m.key,m]));
 const pages=Math.max(1,Math.ceil(decisions.length/60));
 const current=Math.min(page,pages-1);
 const visible=expanded?decisions.slice(current*60,(current+1)*60):decisions.slice(0,4);
 return <>
  <div className="paper-learning"><BrainCircuit size={21}/><div><strong>Öğrenen karar motoru <span className="badge positive">Sanal işlem seçimine bağlı</span></strong><p>Beş yöntem ailesi karşılaştırılır. Öğrenilen sonuçlar giriş seçimini ve risk azaltmayı etkiler. Kapanan sanal işlemlerin komisyon/fonlama sonrası sonucu yeniden öğrenmeye katılır.</p><div className="adaptive-counters"><span><TrendingUp size={13}/>{ml} ML seçici</span><span>{learned.length-ml} istatistiksel seçici</span>{preparing>0&&<span>{preparing} geçmiş değerlendirmesi hazırlanıyor</span>}<span><GitCompareArrows size={13}/>{pending} model adayı</span><span>{feedback} gerçek sanal kapanıştan geri bildirim</span></div></div></div>
  <div className="section-head"><div><h3>Bot şimdi ne düşünüyor?</h3><span>Öğrenilen yöntem seçimi · giriş gerekçesi · mevcut/aday model karşılaştırması</span></div><span className="badge">{decisions.length} analiz</span></div>
  {decisions.length?<div className="table-scroll"><table className="decision-table adaptive-table"><thead><tr><th>Piyasa / zaman dilimi</th><th>Karar ve gerekçesi</th><th>Öğrenme ve karşılaştırma</th><th className="num">Son kontrol</th></tr></thead><tbody>{visible.map(d=>{
   const key=`${d.venue}:${d.symbol}:${d.market}:${d.strategy}`;
   const m=models.get(key);
   return <tr key={key}><td><strong>{d.symbol}</strong><small>{d.venue} · {d.market==='spot'?'Spot':'Vadeli'} · {d.strategy==='intraday'?'15dk':'4s'}</small><small>{regimes[d.regime]||d.regime}</small></td><td><span className={'badge '+(d.accepted?'positive':'blue')}>{d.selected_method?method[d.selected_method]:'Uygun giriş bekleniyor'}</span><small>{d.message}</small>{d.risk_multiplier&&<small>Risk çarpanı ×{n(d.risk_multiplier,2)} · portföy sınırları korunur</small>}{d.next_close&&<small>Sonraki mum: {new Date(d.next_close*1000).toLocaleTimeString('tr-TR',{timeZone:'Europe/Istanbul',hour:'2-digit',minute:'2-digit'})}</small>}</td><td>{m?<><strong>{m.status==='active'?'ML seçimi etkin':'İstatistiksel seçim etkin'}</strong><small>{m.samples} kapanmış tarihsel örnek · {m.feedback_count} sanal geri bildirim</small>{m.qualification&&<small>Maliyetli değerlendirme: {n(m.qualification.net_r)}R · {m.qualification.count} referans işlem</small>}{m.forward&&<small>Aday / mevcut: {m.forward.challenger.count} / {m.forward.champion.count} kapanış · en az {m.forward.minimum}'şer gerekli</small>}<small>{m.message}</small><small>{m.version} · {m.promotions} model kabulü</small></>:<small>Gerçek geçmişten beş yöntem ailesi öğreniliyor…</small>}</td><td className="num"><span className={data.timestamp-d.observed>90?'negative-text':'muted'}>{Math.max(0,Math.floor(data.timestamp-d.observed))} sn önce</span></td></tr>
  })}</tbody></table></div>:<div className="paper-waiting"><BrainCircuit size={17}/>Gerçek geçmiş veriler ve maliyetli işlem örnekleri hazırlanıyor. Bu sırada fiyat ve mevcut pozisyon takibi sürer.</div>}
  {decisions.length>4&&<button className="text-button paper-more" onClick={()=>{setExpanded(!expanded);setPage(0);}}>{expanded?'Daha az göster':`Analizleri sayfalarla incele (${decisions.length})`}</button>}
  {expanded&&<div className="universe-pagination" aria-label="Analiz sayfaları"><span>{current*60+1}–{Math.min((current+1)*60,decisions.length)} / {decisions.length} analiz</span><button className="icon-button" aria-label="Önceki analiz sayfası" disabled={current===0} onClick={()=>setPage(current-1)}><ChevronLeft size={15}/></button><span>{current+1} / {pages}</span><button className="icon-button" aria-label="Sonraki analiz sayfası" disabled={current>=pages-1} onClick={()=>setPage(current+1)}><ChevronRight size={15}/></button></div>}
  {learned.length>0&&<><button className="text-button paper-more" onClick={()=>setFamilies(!families)}>{families?'Yöntem ağırlıklarını gizle':'Öğrenilen yöntem ağırlıklarını göster'}</button>{families&&<div className="adaptive-families">{learned.slice(0,4).map(m=><div key={m.key}><strong>{m.key.replaceAll(':',' · ')}</strong>{m.families.map((f:Row)=><div key={f.method}><span>{f.name}</span><span className={f.paused?'negative-text':f.expected_r>0?'positive-text':'muted'}>{f.paused?'Geçici duraklatıldı':!f.eligible?'Örnek yetersiz':`${n(f.expected_r,2)}R öğrenilen ortalama`}</span></div>)}</div>)}</div>}</>}
  <p className="paper-model-note"><ShieldCheck size={12}/> Öğrenme yalnız sanal hesapta girişleri seçer, veto eder ve riski azaltır. İlk ML kabulü kronolojik maliyetli değerlendirmeye; sonraki model geçişleri eğitimden sonra gelen gerçek fiyatlarla en az 20'şer kapanışa dayanır. Kabul ölçütleri gelecekte daha iyi sonuç garantisi değildir. 1R, referans işlemin başlangıçta planlanan kayıp birimidir; bu karşılaştırmalar birleşik hesap kârı değildir.</p>
 </>
}
