const {_electron:electron}=require('playwright');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const artifacts=path.join(root,'artifacts');
fs.mkdirSync(artifacts,{recursive:true});
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:path.join(artifacts,'chat-ui-data-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
 const app=await electron.launch(process.argv[2]?{executablePath:process.argv[2],args:['--disable-gpu'],env,timeout:60000}:{args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const page=await app.firstWindow();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.getByText('Portföyün bir bakışta.').waitFor({timeout:60000});
  await page.locator('nav').getByRole('button',{name:'AI sohbet',exact:true}).click();
  await page.getByText('Birlikte gözden geçirelim.').waitFor({timeout:15000});
  await page.screenshot({path:path.join(artifacts,'chat-empty-sade-1440.png')});
  const input=page.getByRole('textbox',{name:'Bota mesaj yaz'});
  await input.fill('Bakiyemi özetle. <b>metin</b>');
  await input.press('Enter');
  await page.waitForFunction(async()=>{const r=await window.terminal.request('/chat');return r.messages.some(m=>m.role==='assistant'&&m.status==='done'&&m.content);},{},{timeout:30000});
  await page.locator('.chat-message.assistant .chat-message-bubble p').first().waitFor({timeout:10000});
  assert.equal(await page.locator('.chat-message.user b').count(),0,'Kullanıcı metni HTML olarak yorumlanmamalı');
  assert.match(await page.locator('.chat-message.user').first().innerText(),/<b>metin<\/b>/);
  const before=await page.evaluate(()=>window.terminal.request('/snapshot'));
  const records=await page.evaluate(()=>window.terminal.request('/chat'));
  assert(records.messages.some(m=>m.role==='user'&&m.content.includes('Bakiyemi')));
  assert(records.messages.some(m=>m.role==='assistant'&&m.content&&m.status==='done'));
  assert.equal(await input.inputValue(),'');
  await input.fill('Yeni girişleri durdur');
  await page.getByRole('button',{name:'Mesajı gönder',exact:true}).click();
  await page.locator('.chat-action-card button').first().waitFor({timeout:30000});
  const preview=await page.evaluate(()=>window.terminal.request('/chat'));
  const action=preview.messages.flatMap(m=>m.actions||[]).at(-1);
  assert(action,'Onaylanacak talimat kartı eksik');
  const previewState=await page.evaluate(()=>window.terminal.request('/snapshot'));
  assert.equal(previewState.running,before.running,'Plan tek başına motoru değiştirmemeli');
  const confirm=page.locator('.chat-action-card').last().getByRole('button');
  await confirm.click();
  await page.waitForFunction(async id=>{const r=await window.terminal.request('/chat');return r.messages.flatMap(m=>m.actions||[]).some(a=>a.id===id&&['executed','confirmed','done'].includes(a.status));},action.id,{timeout:30000});
  const after=await page.evaluate(()=>window.terminal.request('/snapshot'));
  assert.equal(after.running,false);
  await page.waitForTimeout(1300);
  assert(await page.locator('.chat-action-card').last().getByRole('button').isDisabled());
  await page.evaluate(()=>{window.__chatOriginalNow=Date.now;Date.now=()=>window.__chatOriginalNow()+130000;});
  await page.waitForTimeout(1200);
  assert.match(await page.locator('.chat-action-card').last().innerText(),/Uygulandı/);
  assert.doesNotMatch(await page.locator('.chat-action-card').last().innerText(),/Süresi doldu/);
  await page.evaluate(()=>{Date.now=window.__chatOriginalNow;delete window.__chatOriginalNow;});
  const checks=[];
  for(const size of [[1440,960],[1280,800]]){
   await app.evaluate(({BrowserWindow},size)=>BrowserWindow.getAllWindows()[0].setSize(...size),size);
   for(const view of ['Sade','Pro']){
    await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:view,exact:true}).click();
    assert(await page.locator('nav').getByRole('button',{name:'AI sohbet',exact:true}).isVisible());
    assert.equal(await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
    const contained=await input.evaluate(el=>{const r=el.getBoundingClientRect();return r.top>=95&&r.bottom<=innerHeight-20;});
    assert(contained,`${view} ${size[0]} mesaj kutusu erişilebilir olmalı`);
    checks.push({size,view,chat:'visible',composer:'in viewport'});
    await page.screenshot({path:path.join(artifacts,`chat-${view.toLowerCase()}-${size[0]}.png`)});
   }
  }
  await input.fill('satır');await input.press('Shift+Enter');
  assert.equal(await input.inputValue(),'satır\n');
  assert.equal(await input.getAttribute('maxlength'),'2000');
  await page.locator('nav').getByRole('button',{name:'Genel bakış',exact:true}).click();
  await page.locator('nav').getByRole('button',{name:'AI sohbet',exact:true}).click();
  await page.locator('.chat-message.assistant').first().waitFor({timeout:10000});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(artifacts,'chat-ui-results.json'),JSON.stringify({version:after.version,checks,factualConversation:'actual account records',previewAndConfirm:'passed',safeText:'passed',enterShiftEnter:'passed',maxLength:2000,historyOnRemount:'passed',localLLM:'disabled in this deterministic UI check',errors},null,2));
  console.log('PASS chat UI: actual records, confirmed action, safe text, composer, both views/two sizes, persistent conversation.');
 }finally{try{await app.evaluate(({app})=>app.quit());}catch{}await app.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
