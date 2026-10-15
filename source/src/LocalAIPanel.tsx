import {useState} from 'react';
import {BrainCircuit,CheckCircle2,FlaskConical,LoaderCircle,RefreshCw} from 'lucide-react';
import type {Row,Snapshot} from './types';

const names:Record<string,string>={ready:'Hazır',ready_to_load:'Yüklemeye hazır',loading:'Model yükleniyor',downloading:'İndiriliyor',missing:'Model dosyaları bulunamadı',disabled:'Kapalı',error:'Son işlem tamamlanamadı'};
const outcomes:Record<string,string>={running:'Deney hesaplanıyor',forward_queue:'İleri dönem karşılaştırma kuyruğunda',insufficient_data:'Eğitim örneği yetersiz',error:'Deney tamamlanamadı'};
export function LocalAIPanel({data}:{data:Snapshot}){
 const [message,setMessage]=useState('');
 const [sending,setSending]=useState(false);
 const ai=data.local_ai;
 if(!ai)return null;
 const report=ai.report||{};
 const experiment=(ai.experiments||[]).at(-1);
 async function refresh(){setSending(true);try{const r=await window.terminal.request(ai.available?'/local-ai-refresh':'/local-ai-install','POST',{});setMessage(r.message);}catch{setMessage('Yerel işlem başlatılamadı.');}finally{setSending(false);}}
 return <div className="local-ai-panel" data-testid="local-ai-panel"><div className="local-ai-heading"><BrainCircuit size={20}/><div><strong>Yerel haber analisti & araştırmacı</strong><small>{ai.model} · bilgisayarında çalışır · ücretli API kullanılmaz</small></div><span className={'badge '+(ai.status==='ready'?'positive':'blue')}>{ai.busy?'Değerlendiriyor':names[ai.status]||ai.status}</span><button className="icon-button" title="Yerel AI ile şimdi değerlendir" disabled={sending||ai.busy||ai.installing||!ai.enabled} onClick={refresh}>{ai.busy?<LoaderCircle size={15} className="spin"/>:<RefreshCw size={15}/>}</button></div>
 {!ai.available&&<button className="button secondary small-button" disabled={sending||ai.installing} onClick={refresh}>Ücretsiz modeli indir · 2,5 GB</button>}
 {ai.installing&&<p className="local-ai-summary">İndirilen: {Math.round((ai.progress.downloaded||0)/1048576)} / {Math.round((ai.progress.total||0)/1048576)} MB</p>}
 {report.summary?<><p className="local-ai-summary">{report.summary}</p><div className="local-ai-assessments">{report.events.map((e:Row)=>{const source=data.news.find(n=>n.id===e.event_id);return <div key={e.event_id}><span className={'badge '+(e.risk==='pause'?'warning':e.risk==='reduce'?'blue':'neutral')}>{e.risk==='pause'?'Giriş bekletme yorumu':e.risk==='reduce'?'Risk azaltma yorumu':'İzleme yorumu'}</span><strong>{source?.title||'Kaynak olayı'}</strong><p>{e.rationale}</p><small>Giriş etkisi: {!ai.enabled||!data.settings.local_ai_news_controls?'Kapalı':data.timestamp-report.created_at>900?'Süresi doldu':e.applied_risk==='pause'?'Süreli bekletme':e.applied_risk==='reduce'?'Risk yarıya iner':'Kısıt uygulanmadı'}</small><small>{source?.source} · AI çıkarımı · doğrulanmış fiyat tahmini değildir</small></div>})}</div><small className="muted text-xs">Son analiz: {new Date(report.created_at*1000).toLocaleString('tr-TR',{timeZone:'Europe/Istanbul'})}. Giriş etkisi yalnız güncel resmî kaynağa bağlı, yeterli güvenli yorumda ve en fazla 15 dakikalık pencereyle uygulanır.</small></>:<p className="local-ai-summary">{ai.message} Oturum çalışırken haberler ve mevcut deney sonuçları birlikte değerlendirilir.</p>}
 {report.knowledge&&<p className="paper-model-note">Son analizin bilgi bağlamı: {report.knowledge.card_ids.length} kaynaklı yöntem kartı · kütüphane {report.knowledge.version}. {report.history_context?.length||0} gerçek uzun dönem özeti sağlandı. Yöntemler ve kaynaklar Stratejiler ekranında görülebilir.</p>}
 {experiment&&<div className="local-ai-experiment"><FlaskConical size={16}/><div><strong>AI tarafından üretilen sınırlı strateji deneyi</strong><p>{experiment.proposal.hypothesis}</p><small>{experiment.proposal.symbol} · {experiment.proposal.venue} · {experiment.proposal.strategy==='intraday'?'15dk':'4s'} · {experiment.proposal.methods.map((m:string)=>({breakout:'Kırılım',momentum:'Momentum',pullback:'Geri çekilme',reversion:'Ortalamaya dönüş',squeeze:'Sıkışma'} as Row)[m]||m).join(', ')}</small><div><span className="badge blue">{outcomes[experiment.status]||experiment.status}</span>{experiment.qualification&&<span className="muted text-xs">Maliyetli dönem: {experiment.qualification.net_r.toFixed(2)}R · {experiment.qualification.count} referans işlem</span>}</div></div></div>}
 {message&&<p className="local-ai-message"><CheckCircle2 size={12}/>{message}</p>}
 <p className="paper-model-note">Dil modelinin ön eğitim ağırlıkları bu bilgisayarda yeniden eğitilmez. Gelişen bölüm; gerçek sonuçları hatırlayan araştırma döngüsü, yöntem seçicileri ve ileri dönem model karşılaştırmasıdır. AI önerisi otomatik emir veya başarı kanıtı değildir.</p>
 </div>
}
