import {useCallback,useEffect,useRef,useState} from 'react';
import {ArrowDown,ArrowRight,BrainCircuit,CheckCircle2,Clock3,Download,LoaderCircle,MessageSquare,Send,Settings2,ShieldCheck,TriangleAlert,UserRound} from 'lucide-react';
import type {Row,Snapshot} from './types';
import './newchat.css';

type ChatMessage={id:string;role:'user'|'assistant';content:string;created_at:number;status?:string;kind?:string;context_at?:number;actions?:Row[];grounding?:Row};
type ChatState={messages:ChatMessage[];busy:boolean;model:Row};
const number=(v:number)=>new Intl.NumberFormat('tr-TR',{maximumFractionDigits:2,minimumFractionDigits:2}).format(v||0);
const time=(v:number)=>new Date(v*1000).toLocaleTimeString('tr-TR',{timeZone:'Europe/Istanbul',hour:'2-digit',minute:'2-digit'});
const modelNames:Record<string,string>={ready:'Yerel model hazır',ready_to_load:'Yerel model yüklenmeye hazır',loading:'Yerel model yükleniyor',downloading:'Yerel model indiriliyor',missing:'Yerel model kurulumu gerekli',disabled:'Yerel model kapalı',error:'Yerel model bekleniyor'};
const actionNames:Record<string,string>={confirmed:'Uygulandı',done:'Uygulandı',executed:'Uygulandı',expired:'Süresi doldu',rejected:'Uygulanmadı',error:'Uygulanamadı',failed:'Uygulanamadı',cancelled:'İptal edildi'};
const kindNames:Record<string,string>={records:'Kayıtlardan',analysis:'Ölçülen göstergeler',ai:'Yerel AI yorumu',plan:'Onay bekleyen plan',result:'İşlem sonucu',unavailable:'Model bilgisi'};
const examples=['Neden işlem açmadın?','Son işlemlerimi özetle','BTC piyasa analizi yap','Yeni girişleri durdur'];

export function ChatPanel({data,openSettings}:{data:Snapshot;openSettings:()=>void}){
 const [chat,setChat]=useState<ChatState>({messages:[],busy:false,model:data.local_ai||{}});
 const [draft,setDraft]=useState('');
 const [loading,setLoading]=useState(true);
 const [sending,setSending]=useState(false);
 const [executing,setExecuting]=useState('');
 const [error,setError]=useState('');
 const [connectionError,setConnectionError]=useState('');
 const [notice,setNotice]=useState('');
 const [installing,setInstalling]=useState(false);
 const [unread,setUnread]=useState(false);
 const alive=useRef(false);
 const fetching=useRef<Promise<ChatState|undefined>|null>(null);
 const sendLock=useRef(false);
 const actionLock=useRef(false);
 const log=useRef<HTMLDivElement>(null);
 const textarea=useRef<HTMLTextAreaElement>(null);
 const nearBottom=useRef(true);
 const lastKey=useRef('');
 const model=chat.model||data.local_ai||{};
 const refresh=useCallback(async()=>{
  if(fetching.current)return fetching.current;
  const operation=(async()=>{
   try{
    const result=await window.terminal.request<ChatState>('/chat');
    if(alive.current){setChat({messages:result.messages||[],busy:!!result.busy,model:result.model||{}});setLoading(false);setConnectionError('');}
    return result;
   }catch{if(alive.current){setLoading(false);setConnectionError('Sohbet bağlantısı kurulamadı. Birazdan yeniden denenecek.');}return undefined;}
   finally{fetching.current=null;}
  })();
  fetching.current=operation;
  return operation;
 },[]);
 useEffect(()=>{
  alive.current=true;let cancelled=false;let timer:number|undefined;
  async function poll(){await refresh();if(!cancelled)timer=window.setTimeout(poll,1000);}
  poll();return()=>{cancelled=true;alive.current=false;window.clearTimeout(timer);};
 },[refresh]);
 useEffect(()=>{
  const latest=chat.messages.at(-1),key=latest?`${latest.id}:${latest.status}:${latest.content}`:'';
  if(lastKey.current===key)return;lastKey.current=key;
  if(nearBottom.current){log.current?.scrollTo({top:log.current.scrollHeight,behavior:'smooth'});setUnread(false);}else setUnread(true);
 },[chat.messages]);
 async function send(value=draft){
  const message=value.trim();if(!message||message.length>2000||sendLock.current||chat.busy)return;
  sendLock.current=true;setSending(true);setError('');setNotice('');
  try{
   const result=await window.terminal.request('/chat','POST',{message});
   if(result.ok===false)throw new Error(result.message||'Mesaj gönderilemedi.');
   if(!alive.current)return;
   setDraft('');nearBottom.current=true;
   // POST records both messages before returning. Wait out an older poll, then fetch accepted messages.
   if(fetching.current)await fetching.current;
   await refresh();textarea.current?.focus();
  }catch(e){if(alive.current)setError(e instanceof Error?e.message:'Mesaj gönderilemedi. Yazdığın metin korunuyor.');}
  finally{sendLock.current=false;if(alive.current)setSending(false);}
 }
 async function execute(action:Row){
  if(actionLock.current)return;actionLock.current=true;setExecuting(action.id);setError('');setNotice('');
  try{
   const result=await window.terminal.request('/chat/action','POST',{id:action.id});
   if(alive.current){if(result.ok===false)setError(result.message||'Talimat uygulanamadı.');else setNotice(result.message||'Talimatın sonucu konuşmaya kaydedildi.');}
   if(fetching.current)await fetching.current;
   await refresh();
  }catch(e){if(alive.current)setError(e instanceof Error?e.message:'Talimat uygulanamadı.');}
  finally{actionLock.current=false;if(alive.current)setExecuting('');}
 }
 async function install(){
  setInstalling(true);setNotice('');try{const result=await window.terminal.request('/local-ai-install','POST',{});if(alive.current)setNotice(result.message||'Model kurulumu başlatıldı.');}catch{if(alive.current)setError('Model kurulumu başlatılamadı.');}finally{if(alive.current)setInstalling(false);}
 }
 function scrollEnd(){nearBottom.current=true;log.current?.scrollTo({top:log.current.scrollHeight,behavior:'smooth'});setUnread(false);}
 const disabled=model.enabled===false||model.status==='disabled';
 const unavailable=!model.available||disabled||model.status==='missing';
 return <section className="chat-page" data-testid="chat-panel">
  <div className="chat-page-heading"><div><div className="eyebrow">YEREL AI ASİSTANIN</div><h1>Botunla konuş.</h1><p>Hesabını sor, analiz iste, işlem planını birlikte değerlendir.</p></div><span className="badge blue"><ShieldCheck size={12}/>{data.mode==='DEMO'?'Demo hesabı':'Sanal hesap'}</span></div>
  <div className="chat-workspace panel">
   <div className="chat-topline"><span className="chat-assistant-icon"><BrainCircuit size={21}/></span><div><strong>Kripto asistanı</strong><small>{model.model||'Bilgisayarında çalışan yerel model'} · ücretli API kullanılmaz</small></div><span className={'chat-model-status '+(model.status==='ready'?'ready':'')}>{chat.busy?<><LoaderCircle size={12} className="spin"/>Yanıt hazırlanıyor</>:<><i className="status-dot"/>{modelNames[model.status]||'Hesap bağlantısı hazır'}</>}</span><button className="icon-button" title="AI ayarlarını aç" aria-label="AI ayarlarını aç" onClick={openSettings}><Settings2 size={16}/></button></div>
   <div className="chat-account-context"><span>{data.mode==='DEMO'?'Örnek Demo hesabı':'Gerçek veri · sanal hesap'}</span><span>Bakiye <strong>{number(data.metrics.equity)} USDT</strong></span><span><strong>{data.positions.length}</strong> açık pozisyon</span><span>{data.running?'Yeni girişler açık':'Yeni girişler duraklatıldı'}</span></div>
   {unavailable&&<div className="chat-model-notice"><BrainCircuit size={16}/><span>{disabled?'Yerel model kapalı.':'Yerel model henüz kullanıma hazır değil.'} Hesap kayıtlarıyla ilgili sorularını sorabilirsin; serbest sohbet ve yorum için yerel model gerekir.</span>{disabled?<button className="text-button" onClick={openSettings}>AI ayarları <ArrowRight size={12}/></button>:<button className="text-button" disabled={installing||model.installing} onClick={install}>{installing||model.installing?<LoaderCircle size={12} className="spin"/>:<Download size={12}/>}Modeli kur</button>}</div>}
   <div className="chat-conversation" ref={log} role="log" aria-label="Botla konuşma geçmişi" aria-live="polite" aria-relevant="additions text" onScroll={()=>{const e=log.current;if(e){nearBottom.current=e.scrollHeight-e.scrollTop-e.clientHeight<80;if(nearBottom.current)setUnread(false);}}}>
    {loading?<div className="chat-loading"><LoaderCircle size={20} className="spin"/>Konuşma hazırlanıyor…</div>:!chat.messages.length?<div className="chat-empty"><span className="chat-empty-icon"><MessageSquare size={30}/></span><h2>Birlikte gözden geçirelim.</h2><p>“Neden işlem açmadın?” diye sorabilir veya belirli bir coin için analiz isteyebilirsin.</p><div className="chat-examples">{examples.map(text=><button key={text} disabled={sending||chat.busy} onClick={()=>send(text)}>{text}<ArrowRight size={13}/></button>)}</div></div>:chat.messages.map(message=><article className={'chat-message '+message.role+(message.status==='error'?' message-error':'')} key={message.id} data-message-id={message.id}>
      <span className="chat-message-avatar">{message.role==='assistant'?<BrainCircuit size={17}/>:<UserRound size={16}/>}</span><div className="chat-message-main"><div className="chat-message-meta"><strong>{message.role==='assistant'?'Kripto asistanı':'Sen'}</strong><time>{time(message.created_at)}</time>{message.role==='assistant'&&message.kind&&kindNames[message.kind]&&<span className="chat-kind-label">{kindNames[message.kind]}</span>}{message.context_at&&<span title="Yanıtın dayandığı hesap ve piyasa bağlamının zamanı">Bağlam {time(message.context_at)}</span>}</div><div className="chat-message-bubble">{message.content&&<p>{message.kind==='ai'?message.content.replace(/\*\*/g,''):message.content}</p>}{message.kind==='ai'&&<small className="chat-ai-note">{message.grounding?.status==='blocked'?'Modelin desteklenmeyen iddiası engellendi; hesapta işlem yapılmadı.':'Nitel AI açıklaması; doğruluğu garanti edilmez. Sayısal hesaplar kayıtlardan ve onay kartından gösterilir.'}</small>}{message.status==='pending'&&<div className="chat-pending"><LoaderCircle size={14} className="spin"/><span>{message.content?'Yanıt tamamlanıyor…':'Sorunu ve güncel kayıtları değerlendiriyorum…'}</span></div>}{message.status==='error'&&<span className="chat-message-error-label"><TriangleAlert size={12}/>Yanıt tamamlanamadı</span>}</div>
       {!!message.actions?.length&&<div className="chat-action-list">{message.actions.map(action=>{
        const proposed=!action.status||['proposed','pending','ready','preview'].includes(action.status);
        const expired=action.status==='expired'||proposed&&!!action.expires_at&&Date.now()/1000>=action.expires_at;
        const available=proposed&&!expired;
        return <section className={'chat-action-card '+(!available?'inactive':'')} key={action.id}><div><ShieldCheck size={15}/><strong>{action.label||'Sanal talimatı onayla'}</strong><span className="badge">{expired?'Süresi doldu':actionNames[action.status]||'Onayın bekleniyor'}</span></div><p>{action.summary}</p>{action.expires_at&&<small><Clock3 size={11}/>{expired?'Geçerlilik sona erdi':'Geçerlilik'} · {time(action.expires_at)} İstanbul</small>}<button className={'button '+(available?'primary':'secondary')} disabled={!available||!!executing||sending} onClick={()=>execute(action)}>{executing===action.id?<LoaderCircle size={13} className="spin"/>:<CheckCircle2 size={13}/>} {available?(action.label||'Sanal talimatı onayla'):expired?'Süresi doldu':actionNames[action.status]||'Tamamlandı'}</button></section>;
       })}</div>}
      </div></article>)}
   </div>
   {unread&&<button className="chat-new-message" onClick={scrollEnd}><ArrowDown size={13}/>Yeni mesaja git</button>}
   <div className="chat-compose-area">{(error||connectionError||notice)&&<div className={'chat-feedback '+(error||connectionError?'error':'')} role="status">{error||connectionError?<TriangleAlert size={14}/>:<CheckCircle2 size={14}/>}<span>{error||connectionError||notice}</span></div>}<form onSubmit={e=>{e.preventDefault();send();}}><label className="sr-only" htmlFor="chat-message-input">Bota mesaj yaz</label><textarea id="chat-message-input" ref={textarea} maxLength={2000} rows={2} value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Botuna sor veya bir işlem planı iste…" onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send();}}}/><button className="chat-send" type="submit" aria-label="Mesajı gönder" disabled={!draft.trim()||sending||chat.busy}>{sending?<LoaderCircle size={18} className="spin"/>:<Send size={18}/>}</button></form><div className="chat-compose-foot"><span>Enter gönderir · Shift + Enter yeni satır</span><span>{draft.length}/2000</span></div><p className="chat-scope-note">Talimatlar önce plan olarak gösterilir. Onayladığında güncel bakiye ve risk sınırları yeniden kontrol edilir.</p></div>
  </div>
 </section>;
}
