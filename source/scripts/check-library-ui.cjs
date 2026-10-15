const {_electron:electron}=require('playwright');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:path.join(root,'artifacts','library-ui-data-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
 const app=await electron.launch({args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const p=await app.firstWindow();
  await p.getByText('Portföyün bir bakışta.').waitFor({timeout:60000});
  await p.locator('nav').getByRole('button',{name:'Stratejiler',exact:true}).click();
  const cards=p.locator('.knowledge-card');
  await cards.first().waitFor({timeout:10000});
  const count=await cards.count();assert(count>=12);
  await cards.evaluateAll(items=>items.forEach(card=>card.open=true));
  assert(await p.locator('.knowledge-sources button').count()>=count);
  const checks=[];
  for(const size of [[1440,960],[1280,800]]){
   await app.evaluate(({BrowserWindow},size)=>BrowserWindow.getAllWindows()[0].setSize(...size),size);
   for(const view of ['Sade','Pro']){
    await p.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:view,exact:true}).click();
    assert.equal(await p.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
    const bad=await p.locator('.knowledge-sources button').evaluateAll(buttons=>buttons.filter(b=>{const r=b.getBoundingClientRect(),host=b.closest('.knowledge-card').getBoundingClientRect();return r.right>host.right+1||r.left<host.left;}).length);assert.equal(bad,0);
    checks.push({size,view,cards:count,sources:'contained'});
   }
  }
  await p.locator('.research-heading').scrollIntoViewIfNeeded();
  await p.screenshot({path:path.join(root,'artifacts','presentation-library-sources-1280.png')});
  await p.getByLabel('Kütüphanede yöntem ara').fill('VWAP');
  assert.equal(await cards.count(),1);
  await p.getByLabel('Kütüphanede yöntem ara').fill('');
  await p.getByLabel('Kütüphane durumu').selectOption('methodology');
  assert(await cards.count()>0);
  fs.writeFileSync(path.join(root,'artifacts','library-ui-results.json'),JSON.stringify({checks,search:'passed',statusFilter:'passed',externalSourceButtons:'layout checked; did not launch browser'},null,2));
  console.log('PASS library UI: cards/sources both views and sizes, search, status filter.');
 }finally{try{await app.evaluate(({app})=>app.quit());}catch{}await app.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
