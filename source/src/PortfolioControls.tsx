import {ShieldCheck,Layers3,Zap,SlidersHorizontal} from 'lucide-react';
import type {Snapshot} from './types';

export function PortfolioControls({data,busy,choose}:{data:Snapshot;busy:boolean;choose:(id:string)=>void}){
 const s=data.settings;
 const icons={safe:ShieldCheck,balanced:Layers3,aggressive:Zap,mixed:SlidersHorizontal};
 return <section className="panel portfolio-controls" data-testid="portfolio-controls">
  <div className="section-head"><div><h3>İşlem tarzı ve coin havuzu</h3><span>{s.allowlist.length} coin izleniyor · {data.universe?.eligible||0} coinde güncel ve yeterli hacimli piyasa · {data.universe?.analyzed||0} / {data.universe?.expected||0} analiz hazır</span></div><span className="badge blue">{data.positions.length} / {s.max_positions} açık pozisyon</span></div>
  <div className="profile-grid">{Object.entries(data.risk_profiles||{}).map(([id,p])=>{const Icon=icons[id as keyof typeof icons];return <button key={id} disabled={busy} aria-pressed={s.risk_profile===id} className={'profile-option '+(s.risk_profile===id?'selected':'')} onClick={()=>choose(id)}><span><Icon size={17}/><strong>{p.name}</strong>{s.risk_profile===id&&<span className="profile-selected">Seçili</span>}</span><small>En fazla {p.max_positions} pozisyon · toplam risk %{p.total_risk}</small><small>{id==='mixed'?'İşleme göre küçük / orta / atak pay':`İşlem riski ≤ %${p.trade_risk} · ${p.leverage}x tavan`}</small></button>})}</div>
  <div className="portfolio-limit-row"><span>Etkin işlem tavanı <strong>%{s.trade_risk}</strong></span><span>Tek coin <strong>%{s.symbol_risk}</strong></span><span>Bağlantılı coinler <strong>%{s.correlated_risk}</strong></span><span>Günlük kayıp <strong>%{s.daily_loss}</strong></span><span>Kaldıraç <strong>≤ {s.leverage}x isolated</strong></span></div>
  <p className="muted text-xs">İşlem büyüklüğü yeni girişlerde değişir; portföy kayıp eşikleri hemen uygulanır. Açık işlemler büyütülmez. Karma modda yeni yöntem küçük başlar. Korelasyon verisi eksikse ortak risk bütçesi kullanılır. Sayılar tavanlardır; yeterli sinyal ve bakiye olmadan pozisyon açılmaz.</p>
 </section>
}
