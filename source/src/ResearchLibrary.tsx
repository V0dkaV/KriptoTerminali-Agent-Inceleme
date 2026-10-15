import {useState} from 'react';
import {BookOpen,ExternalLink,Search} from 'lucide-react';
import type {Row,Snapshot} from './types';
import './research-library.css';

const labels:Record<string,string>={adaptive:'Seçicide uygulanıyor',research:'Araştırma adayı',methodology:'Doğrulama ilkesi'};
export function ResearchLibrary({data}:{data:Snapshot}){
 const [query,setQuery]=useState('');
 const [filter,setFilter]=useState('all');
 const [message,setMessage]=useState('');
 const library=data.knowledge;
 if(!library)return null;
 const cards=library.cards.filter((c:Row)=>(filter==='all'||c.status===filter)&&
   `${c.name} ${c.family} ${c.method}`.toLocaleLowerCase('tr-TR').includes(query.toLocaleLowerCase('tr-TR')));
 const report=data.local_ai?.report||{};
 const provided=report.knowledge?.card_ids||[];
 const cited=report.knowledge_ids||[];
 async function open(url:string){try{await window.terminal.openExternal(url);setMessage('');}catch{setMessage('Kaynak açılamadı. Bağlantıyı kullanım rehberinde de bulabilirsin.');}}
 return <section className="research-library" aria-label="Kaynaklı analiz kütüphanesi">
  <div className="research-heading"><BookOpen size={23}/><div><h2>Kaynaklı analiz kütüphanesi</h2><p>{library.cards.length} yöntem ve doğrulama kartı · gözden geçirme: {library.reviewed_at} · sürüm {library.version}</p></div></div>
  <p className="research-intro">Yerel AI her değerlendirmede bu kütüphaneden sınırlı bir seçki alır. Yöntemin tanımını bilmek, o yöntemin bu botta başarılı olduğunu göstermez. Araştırma adayları işlem açamaz.</p>
  <div className="research-controls"><label><Search size={15}/><input aria-label="Kütüphanede yöntem ara" placeholder="VWAP, fonlama, momentum…" value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label="Kütüphane durumu" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">Tüm kartlar</option>{Object.entries(labels).map(([id,label])=><option value={id} key={id}>{label}</option>)}</select><small>{cards.length} kart</small></div>
  <div className="knowledge-grid">{cards.map((c:Row)=><details className="panel knowledge-card" key={c.id}><summary><span className={'badge '+(c.status==='adaptive'?'positive':c.status==='methodology'?'blue':'neutral')}>{labels[c.status]}</span><h3>{c.name}</h3><p>{c.family}</p><span className="knowledge-expand">Yöntem, veri ve kaynaklar</span></summary><div className="knowledge-body"><p>{c.method}</p><dl><dt>Gerekli veri</dt><dd>{c.data}</dd><dt>Sınırlar</dt><dd>{c.limitation}</dd><dt>Doğrulama durumu</dt><dd>{c.validation}</dd></dl><div className="knowledge-sources">{c.source_ids.map((id:string)=>{const source=library.sources.find((s:Row)=>s.id===id);return source?<button className="text-button" key={id} onClick={()=>open(source.url)}>{source.title}<ExternalLink size={12}/></button>:null;})}</div></div></details>)}</div>
  {!cards.length&&<p className="muted">Bu aramayla eşleşen kart yok.</p>}
  <div className="panel knowledge-context"><strong>AI bu bilgiyi nasıl kullanıyor?</strong><p>{library.learning} {library.update_policy}</p>{provided.length?<><p>Son analize verilen kartlar: {provided.map((id:string)=>library.cards.find((c:Row)=>c.id===id)?.name||id).join(', ')}.</p><p>Modelin yanıtında işaretlediği kartlar: {cited.length?cited.map((id:string)=>library.cards.find((c:Row)=>c.id===id)?.name||id).join(', '):'Belirtilmedi; yukarıdaki liste yalnız sağlanan bağlamdır.'}</p></>:<p>Bu sürümün kütüphanesiyle henüz tamamlanmış bir AI değerlendirmesi yok.</p>}<p>6 ay / 1 yıl grafik özeti, açtığın gerçek geçmişlerden alınır. Bu arşiv, kısa dönem öğrenen seçicinin eğitim penceresini otomatik olarak değiştirmez.</p></div>
  {message&&<p role="status">{message}</p>}
 </section>
}
