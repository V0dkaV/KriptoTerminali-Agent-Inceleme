import {useState} from 'react';
import {Activity,ArrowRight,BrainCircuit,Clock3,Play,Radio,RefreshCw,ShieldCheck,Wallet} from 'lucide-react';
import type {Snapshot} from './types';
import {AdaptiveLearning} from './AdaptiveLearning';
import {LocalAIPanel} from './LocalAIPanel';
import {ExecutionStatus} from './ExecutionStatus';

const number=(v:number,d=2)=>new Intl.NumberFormat('tr-TR',{maximumFractionDigits:d,minimumFractionDigits:d}).format(v||0);
const regime:Record<string,string>={uptrend:'Yükseliş trendi',downtrend:'Düşüş trendi',range:'Yatay piyasa',volatile:'Yüksek oynaklık',unavailable:'Veri bekleniyor'};

export function PaperSession({data,busy,start,resume}:{data:Snapshot;busy:boolean;start:(balance:number)=>void;resume:()=>void}){
  const [balance,setBalance]=useState('10000');
  const [editing,setEditing]=useState(false);
  const active=data.mode==='PAPER'&&!!data.session?.started_at;
  const setup=!active||editing;
  const now=data.timestamp;
  const markets=data.mode==='PAPER'?data.markets:[];
  const fresh=markets.filter(q=>now-q.observed<15);
  const streamed=fresh.filter(q=>now-(q.stream_observed||0)<10);
  const models=data.learning?.filter(r=>r.status==='observing')||[];
  const decisions=(data.decisions||[]).slice().sort((a,b)=>b.observed-a.observed);
  const count=decisions.length;
  return <section className="panel paper-session" data-testid="paper-session">
    <div className="paper-session-top"><div className="paper-session-icon"><Radio size={24}/></div><div className="paper-session-title"><div className="eyebrow">GERÇEK PİYASA · SANAL PARA</div><h2>{active?'Botun portföyünü birlikte izleyelim.':'Sanal paranı ver, bot piyasayı izlesin.'}</h2><p>Binance ve Bybit fiyatlarıyla otomatik işlem. Borsa hesabı veya API anahtarı gerekmiyor.</p></div><span className={'badge '+(streamed.length?'positive':'blue')}>{streamed.length?'● Anlık bağlantı':fresh.length?'REST fiyat akışı':'Bağlantı hazırlanıyor'}</span></div>
    {setup?<div className="paper-start-form"><label className="field"><span>Başlangıç sanal bakiyesi · USDT</span><input aria-label="Başlangıç sanal bakiyesi" type="number" min="100" max="10000000" step="100" value={balance} onChange={e=>setBalance(e.target.value)}/></label><button className="button primary" disabled={busy||Number(balance)<100||Number(balance)>10000000||!Number.isFinite(Number(balance))} onClick={()=>{start(Number(balance));setEditing(false);}}><Play size={15}/>{active?'Yeni sanal oturum başlat':'Gerçek veride başlat'}<ArrowRight size={15}/></button>{editing&&<button className="button subtle" onClick={()=>setEditing(false)}>Vazgeç</button>}<small>Seçili profil: {data.risk_profiles?.[data.settings.risk_profile]?.name||'Özel'} · en fazla {data.settings.leverage}x · işlem tavanı %{data.settings.trade_risk}<br/>Yeni oturumda önceki sonuçlar yerel arşivde korunur.</small></div>:<div className="paper-session-summary"><div><Wallet size={17}/><span>Verdiğin bakiye<strong>{number(data.metrics.initial)} USDT</strong></span></div><div><Activity size={17}/><span>Kapanan işlem<strong>{data.metrics.closed_count} işlem · {data.metrics.liquidations||0} tahmini tasfiye</strong></span></div><div><Clock3 size={17}/><span>Güncel veri<strong>{fresh.length} güncel kotasyon · {streamed.length} anlık akış</strong></span></div>{!data.running&&<button className="button primary" disabled={busy||!!data.halt} onClick={resume}><Play size={14}/>Oturumu sürdür</button>}<button className="text-button" disabled={busy||data.positions.length>0} onClick={()=>setEditing(true)}><RefreshCw size={13}/>Yeni bakiye / oturum</button></div>}
    <div className="paper-explainer"><ShieldCheck size={16}/><span>Stop, hedef, komisyon ve fonlama izlenir. Vadeli tasfiye: işaret fiyatı ve sabit %1 bakım teminatı varsayımıyla tahmin edilir. Bilgisayar açık ve internete bağlı olmalı.</span></div>
    {active&&<><ExecutionStatus data={data}/><LocalAIPanel data={data}/><AdaptiveLearning data={data}/></>}
  </section>
}
