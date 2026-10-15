import type {Row} from './types';

const number=(v:unknown,d=2)=>typeof v==='number'&&Number.isFinite(v)?new Intl.NumberFormat('tr-TR',{maximumFractionDigits:d,minimumFractionDigits:d}).format(v):'—';
const date=(v:unknown)=>typeof v==='number'&&v>0?new Date(v*1000).toLocaleDateString('tr-TR',{timeZone:'Europe/Istanbul',day:'2-digit',month:'short',year:'numeric'}):'—';
export function HistorySummary({history,error,detailed=false}:{history:Row;error:string;detailed?:boolean}){
 const c=history.coverage||{},s=history.summary||{},r=history.range||{};
 const trend=({up:'Yükseliş',down:'Düşüş',mixed:'Karışık',insufficient:'Veri yetersiz'} as Row)[s.trend]||'Veri yetersiz';
 return <section className="history-summary" data-testid="history-summary" aria-label="Uzun dönem grafik analizi">
  <div className="history-coverage"><strong>{r.months===12?'1 yıllık':'6 aylık'} geçmiş analizi</strong><span className={'badge '+(c.status==='complete'&&!history.stale?'positive':'warning')}>{history.source==='DEMO'?'Örnek veri · ':''}{c.status==='complete'?'Dönem tamam':c.status==='partial'?'Eksik geçmiş':'Geçmiş alınamadı'}{history.stale?' · Önbellek':''}</span></div>
  <p>Gösterilen: {date(c.start)} – {date(c.end)} · {c.actual||0} / {c.expected||0} kapanmış mum. İstenen: {date(r.requested_start)} – {date(r.requested_end)}.</p>
  <div className="history-metrics"><div><span>Dönem getirisi</span><strong>{number(s.return_pct)}%</strong></div><div><span>En büyük fiyat düşüşü</span><strong>{number(s.max_drawdown_pct)}%</strong></div><div><span>Trend görünümü</span><strong>{trend}</strong></div><div><span>Günlük EMA bağlamı</span><strong>{({up:'Yükseliş',down:'Düşüş',mixed:'Karışık',insufficient:'Veri yetersiz'} as Row)[s.daily_context?.trend]||'Veri yetersiz'}</strong></div></div>
  {detailed&&<div className="history-metrics"><div><span>Dönem en düşük / en yüksek</span><strong>{number(s.low,s.low<1?6:2)} / {number(s.high,s.high<1?6:2)}</strong></div><div><span>Yıllıklandırılmış oynaklık</span><strong>{number(s.annualized_volatility_pct)}%</strong></div><div><span>Son 7 gün / önceki 7 gün hacmi</span><strong>×{number(s.volume_recent_vs_previous)}</strong></div><div><span>EMA hazırlığı / günlük bağlam</span><strong>{c.warmup_actual||0} / {c.warmup_required||200} · {s.daily_context?.observations||0} günlük mum</strong></div></div>}
  {c.status!=='complete'&&<p className="history-warning">{c.missing||0} eksik mum · {c.gaps?.length||0} veri boşluğu. Mevcut gerçek veriler gösterilir; eksikler doldurulmuş gibi kabul edilmez.</p>}
  {error&&<p className="history-warning">{error}</p>}
  {s.limitations?.length>0&&<ul>{s.limitations.map((text:string)=><li key={text}>{text}</li>)}</ul>}
  <p className="history-footnote">Bu, fiyat geçmişinin betimleyici analizidir; strateji getirisi veya kâr tahmini değildir. Canlı girişler ayrı risk ve strateji kontrollerinden geçer.</p>
 </section>
}
