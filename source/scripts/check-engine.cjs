const {spawn,spawnSync}=require('node:child_process');
const path=require('node:path');
const fs=require('node:fs');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const token=crypto.randomBytes(32).toString('hex');
const dir=path.join(root,'artifacts','binary-test-'+Date.now());
const binary=process.argv[2]||path.join(root,'engine-dist','kripto-engine','kripto-engine.exe');
const child=spawn(binary,['--data-dir',dir],{windowsHide:true,env:{...process.env,KRIPTO_DISABLE_LOCAL_AI:'1'},stdio:['pipe','pipe','pipe']});
child.stdin.end(JSON.stringify({token})+'\n');
let log='',error='';
child.stdout.on('data',c=>log+=c.toString());
child.stderr.on('data',c=>error+=c.toString());
async function waitFor(fn,ms=60000){const start=Date.now();while(Date.now()-start<ms){const r=await fn();if(r)return r;await new Promise(r=>setTimeout(r,250));}throw new Error('Timeout: '+error.slice(-1500));}
(async()=>{
  try{
    const match=await waitFor(()=>log.match(/KRIPTO_READY (\{[^\n]+\})/));
    const base='http://127.0.0.1:'+JSON.parse(match[1]).port;
    async function call(route,body){const r=await fetch(base+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const value=await r.json();assert(r.ok,JSON.stringify(value));return value;}
    await waitFor(async()=>{try{return (await call('/health')).ok;}catch{return false;}});
    assert.equal((await fetch(base+'/snapshot')).status,401);
    const state=await call('/snapshot');assert.equal(state.mode,'PAPER');assert.equal(state.version,'0.8.0');
    assert.equal(state.knowledge.cards.length,14);
    const chat=await call('/chat',{message:'Hesabımı özetle'});assert(chat.ok);
    const reply=await waitFor(async()=>{const c=await call('/chat');return c.messages.find(m=>m.id===chat.id&&m.status==='done');});
    assert.equal(reply.kind,'records');assert(reply.content.includes('10.000,00'));
    const proposed=await call('/chat',{message:'Yeni girişleri durdur'});assert(proposed.ok);
    const plan=await waitFor(async()=>{const c=await call('/chat');return c.messages.find(m=>m.id===proposed.id&&m.actions.length);});
    const receipt=await call('/chat/action',{id:plan.actions[0].id});assert(receipt.ok);
    assert.deepEqual(await call('/chat/action',{id:plan.actions[0].id}),receipt);
    const missionPlan=await call('/operations/plan',{capital:100,leverage:2,max_positions:2,duration_hours:24});assert(missionPlan.ok);
    assert.equal((await call('/operations')).mission,null);
    const missionReceipt=await call('/chat/action',{id:missionPlan.action.id});assert(missionReceipt.ok);
    assert.deepEqual(await call('/chat/action',{id:missionPlan.action.id}),missionReceipt);
    assert.equal((await call('/operations')).mission.capital,100);
    assert((await call('/operations/pause',{})).ok);
    await call('/command',{kind:'mode',payload:{mode:'DEMO'}});
    const history=await call('/history?symbol=BTCUSDT&venue=Binance&market=spot&months=12&interval=1d');
    assert.equal(history.source,'DEMO');assert.equal(history.coverage.status,'complete');assert(history.rows.length>=364);
    await call('/command',{kind:'mode',payload:{mode:'PAPER'}});
    const job=await call('/jobs',{kind:'backtest',strategy:'intraday',symbol:'BTCUSDT',venue:'Binance',market:'spot',source:'DEMO',months:7,fee_bps:10,slippage_bps:3});
    assert(job.ok);
    const done=await waitFor(async()=>{const s=await call('/snapshot');const j=s.jobs.find(j=>j.id===job.id);if(j.status==='error')throw new Error(j.message+'\n'+error);return j.status==='done'?j:null;});
    const report=await call('/report/'+job.id);
    assert.equal(report.source,'DEMO');
    const ml=await call('/jobs',{kind:'ml',strategy:'intraday',symbol:'BTCUSDT',venue:'Binance',market:'spot',source:'DEMO',months:36,fee_bps:10,slippage_bps:3});
    assert(ml.ok);
    await waitFor(async()=>{const s=await call('/snapshot');const j=s.jobs.find(j=>j.id===ml.id);if(j.status==='error')throw new Error(j.message+'\n'+error);return j.status==='done';},90000);
    const model=await call('/report/'+ml.id);
    assert(model.model_sha256);
    fs.writeFileSync(path.join(root,'artifacts','binary-results.json'),JSON.stringify({version:state.version,knowledgeCards:state.knowledge.cards.length,history:'passed',conversation:'passed',operations:'passed',health:true,unauthorizedRejected:true,backtest:done.status,ml:'passed',modelHash:model.model_sha256,standalonePython:true},null,2));
    console.log('PASS: standalone EXE, authenticated API, isolated backtest worker, ML training and model persistence.');
    await call('/shutdown',{});
    await waitFor(()=>child.exitCode!==null,15000);
  }finally{if(child.exitCode===null)spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
