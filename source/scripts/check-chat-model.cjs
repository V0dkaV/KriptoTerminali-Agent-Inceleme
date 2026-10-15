const {_electron:electron}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DATA_DIR:path.join(root,'artifacts','chat-model-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;delete env.KRIPTO_DISABLE_LOCAL_AI;
(async()=>{
 const app=await electron.launch(process.argv[2]?{executablePath:process.argv[2],args:['--disable-gpu'],env,timeout:60000}:{args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const p=await app.firstWindow();const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.getByText('Portföyün bir bakışta.').waitFor({timeout:60000});
  await p.locator('nav').getByRole('button',{name:'AI sohbet',exact:true}).click();
  const before=await p.evaluate(()=>window.terminal.request('/snapshot'));
  const input=p.getByRole('textbox',{name:'Bota mesaj yaz'});
  await input.fill('Merhaba. Benimle hangi verilere dayanarak konuşabiliyorsun, işlem yapmadan önce nasıl bir plan göstereceksin? Kısaca açıkla.');
  await p.getByRole('button',{name:'Mesajı gönder',exact:true}).click();
  let chat,answer;
  for(let i=0;i<240;i++){
   await p.waitForTimeout(1000);chat=await p.evaluate(()=>window.terminal.request('/chat'));
   if(i%30===0)console.log(JSON.stringify({seconds:i,status:chat.model.status,busy:chat.busy,device:chat.model.device}));
   answer=chat.messages.find(m=>m.role==='assistant'&&m.status!=='pending');if(answer)break;
  }
  assert(answer, 'No local conversation response');
  assert.equal(answer.status,'done',answer.content);assert.equal(answer.kind,'ai',answer.content);
  assert(answer.content.length>20);assert.equal(answer.actions.length,0);
  assert(chat.model.available&&!chat.model.paid_api);
  await p.waitForTimeout(1300);
  await p.screenshot({path:path.join(root,'artifacts','chat-real-local-ai.png')});
  const r=await p.evaluate(()=>window.terminal.request('/chat','POST',{message:'BTC piyasa analizi yap'}));assert(r.ok);
  let analysis;
  for(let i=0;i<60;i++){
   await p.waitForTimeout(500);chat=await p.evaluate(()=>window.terminal.request('/chat'));
   analysis=chat.messages.find(m=>m.id===r.id&&m.status!=='pending');if(analysis)break;
  }
  assert(analysis&&analysis.kind==='analysis',analysis?.content);assert.match(analysis.content,/EMA20/);
  const after=await p.evaluate(()=>window.terminal.request('/snapshot'));
  assert.equal(after.running,before.running);assert.equal(after.positions.length,0);assert.equal(after.metrics.initial,before.metrics.initial);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(root,'artifacts','chat-model-results.json'),JSON.stringify({version:after.version,time:new Date().toISOString(),model:chat.model,answer,analysis,accountUnchanged:true,errors},null,2));
  console.log('PASS: actual local Qwen conversation, current real BTC candle analysis, no orders or account changes.');
 }finally{try{await app.evaluate(({app})=>app.quit());}catch{}await app.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
