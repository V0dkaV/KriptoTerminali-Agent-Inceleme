import {Activity,Clock3,ListFilter,ShieldCheck,TriangleAlert} from 'lucide-react';
import type {Snapshot} from './types';
import './execution-status.css';

const count=(value:number|undefined)=>Math.max(0,Math.floor(value||0)).toLocaleString('tr-TR');
const age=(value:number|null|undefined)=>value==null?'Henüz ölçülmedi':value<1?'1 sn altında':`${count(value)} sn önce`;

export function ExecutionStatus({data}:{data:Snapshot}){
 const status=data.execution;
 if(!status)return null;
 const training=status.training;
 const analysis=status.analysis;
 const reasons=status.reasons||[];
 const gate=status.entry_gate;
 const capital=new Intl.NumberFormat('tr-TR',{maximumFractionDigits:2}).format(status.capital||0);
 return <section className="execution-status" data-testid="execution-status" aria-label="İşlem motorunun çalışma durumu">
  <div className="execution-status-heading"><Activity size={18}/><div><h3>İşlem neden açılmıyor?</h3><p>Fiyat ve pozisyon kontrolü, giriş analizi ve yerel AI ayrı işlerdir.</p></div><span className={'badge '+(gate?.blocked?'warning':data.running?'positive':'blue')}>{gate?.blocked?gate.label:data.running?'Motor etkin':'Yeni girişler duraklatıldı'}</span></div>
  {gate?.blocked&&<div className="execution-entry-gate" role="status" data-testid="execution-entry-gate" data-gate-code={gate.code}><TriangleAlert size={14}/><span>{gate.message}</span></div>}
  <div className="execution-stage-grid">
   <div><span><Activity size={13}/>Fiyat / pozisyon kontrolü</span><strong data-testid="execution-heartbeat">{age(status.heartbeat_age)}</strong><small>{count(status.positions)} açık pozisyon · {capital} USDT başlangıç</small></div>
   <div><span><ListFilter size={13}/>Giriş analizi</span><strong data-testid="execution-analysis">{count(analysis.completed)} / {count(analysis.expected)} analiz</strong><small>Kapanmış {(status.signal_intervals||['15m','4h']).map(interval=>interval==='15m'?'15 dk':interval==='4h'?'4 saat':interval).join(' / ')} mumları kullanılır.</small></div>
   <div><span><Clock3 size={13}/>Arka plan öğrenmesi</span><strong data-testid="execution-training">{training.running?'Model hazırlanıyor':training.queued?'Sıradaki model bekleniyor':'Eğitim çalışmıyor'}</strong><small>{count(training.queued)} sırada · {count(training.completed)} tamamlandı{training.last_duration!=null&&training.last_duration>0?` · son eğitim ${training.last_duration<1?'1 sn altında':`${count(training.last_duration)} sn`}`:''}</small></div>
  </div>
  <div className="execution-reasons" aria-label="Son giriş kararlarının özeti">{reasons.length?reasons.slice(0,5).map(reason=><span key={reason.code} data-reason-code={reason.code}><strong>{count(reason.count)}</strong>{reason.label}</span>):<span>İlk analiz sonuçları bekleniyor.</span>}{status.approved>0&&<span><strong>{count(status.approved)}</strong>onaylı fırsat</span>}</div>
  <p className="execution-status-note"><ShieldCheck size={13}/>{status.model_note||'Yerel AI sohbet ve araştırma içindir. Sayısal işlem motoru, giriş koşulları ve risk sınırları uygunsa emir açar.'}</p>
 </section>;
}
