const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, safeStorage, shell, dialog } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

if (require('electron-squirrel-startup')) app.quit();
if (process.env.KRIPTO_DATA_DIR) app.setPath('userData', process.env.KRIPTO_DATA_DIR);
const single = app.requestSingleInstanceLock();
if (!single) app.quit();
let win, tray, child, endpoint, quitting = false, backendReady = false;
const token = crypto.randomBytes(32).toString('hex');
const allowed = new Set(['/snapshot','/quote','/history','/chat','/chat/action','/operations','/operations/plan','/operations/pause','/command','/settings','/jobs','/connect','/news-refresh','/universe-refresh','/telegram-test','/research-proposal','/local-ai-refresh','/local-ai-install']);
const dataDir = path.join(app.getPath('userData'), 'data');
const vaultPath = path.join(app.getPath('userData'), 'vault.enc');
const iconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" rx="16" fill="#0f1c31"/><path d="M16 44V20h7v13l8-13h9L30 35l12 9H30l-7-6v6z" fill="#4adecb"/><path d="M43 18v15h6V18z" fill="#649bff"/></svg>';
function icon() {
  const file=path.join(__dirname,'../assets/icon.png');
  return fs.existsSync(file)?nativeImage.createFromPath(file):nativeImage.createFromDataURL('data:image/svg+xml;base64,'+Buffer.from(iconSvg).toString('base64'));
}
function readVault() {
  try {
    if (!fs.existsSync(vaultPath)) return {};
    if (!safeStorage.isEncryptionAvailable()) return {};
    return JSON.parse(safeStorage.decryptString(fs.readFileSync(vaultPath)));
  } catch { return {}; }
}
function writeVault(vault) {
  if (!safeStorage.isEncryptionAvailable()) throw new Error('Windows korumalı depolaması kullanılamıyor.');
  const temp=vaultPath+'.tmp';
  fs.writeFileSync(temp,safeStorage.encryptString(JSON.stringify(vault)));
  fs.renameSync(temp,vaultPath);
}
async function request(route, method='GET', body) {
  if (!backendReady) throw new Error('İşlem motoru hazırlanıyor.');
  const res=await fetch(endpoint+route, {
    method, headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},
    body:body===undefined?undefined:JSON.stringify(body), signal:AbortSignal.timeout(route.startsWith('/history?')?120000:route.includes('research-proposal')?55000:30000)
  });
  const value=await res.json();
  if (!res.ok) throw new Error(typeof value.detail==='string'?value.detail:'İstek doğrulanamadı.');
  return value;
}
function startBackend() {
  fs.mkdirSync(dataDir,{recursive:true});
  const executable=app.isPackaged?path.join(process.resourcesPath,'kripto-engine','kripto-engine.exe'):path.join(__dirname,'../.venv/Scripts/python.exe');
  const args=app.isPackaged?['--data-dir',dataDir]:['-m','engine.main','--data-dir',dataDir];
  const vault=readVault();
  child=spawn(executable,args,{cwd:app.isPackaged?process.resourcesPath:path.join(__dirname,'..'),windowsHide:true,stdio:['pipe','pipe','pipe'],
    env:{...process.env,PYTHONUTF8:'1',PYTHONUNBUFFERED:'1'}});
  // The retained pipe is an ownership lease: EOF makes the engine stop if this
  // desktop process disappears, including crashes and forced termination.
  child.stdin.on('error',()=>{});
  child.stdin.write(JSON.stringify({token,credentials:vault.credentials||{},telegram:vault.telegram,ai:vault.ai,watch_parent:true})+'\n');
  let buffer='';
  child.stdout.on('data',async chunk=>{
    buffer+=chunk.toString();
    const lines=buffer.split('\n'); buffer=lines.pop();
    for (const line of lines) {
      if (line.startsWith('KRIPTO_READY ')) {
        try {
          const {port}=JSON.parse(line.slice(13));
          if (!Number.isInteger(port)||port<1024||port>65535) return;
          endpoint='http://127.0.0.1:'+port;
          for(let i=0;i<100;i++) {
            try { const r=await fetch(endpoint+'/health',{headers:{Authorization:'Bearer '+token}}); if(r.ok){backendReady=true;break;} } catch {}
            await new Promise(r=>setTimeout(r,100));
          }
        } catch {}
      }
    }
  });
  child.stderr.on('data',()=>{}); // Never persist request payloads or credentials.
  child.on('error',()=>{backendReady=false; win?.webContents.send('engine-state',{ready:false,error:'Yerel motor başlatılamadı.'});});
  child.on('exit',()=>{backendReady=false; if(!quitting)win?.webContents.send('engine-state',{ready:false,error:'İşlem motoru durdu. Uygulamayı yeniden açın.'});});
}
function createWindow() {
  win=new BrowserWindow({width:1440,height:960,minWidth:1280,minHeight:800,title:'Kripto Terminali',
    frame:false,backgroundColor:'#080e1b',icon:icon(),show:!process.env.KRIPTO_TEST_HIDDEN,
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
  win.setMenuBarVisibility(false);
  win.webContents.session.webRequest.onHeadersReceived((details,callback)=>callback({responseHeaders:{...details.responseHeaders,
    'Content-Security-Policy':["default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'none'; object-src 'none'; frame-src 'none'"]}}));
  win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  win.webContents.on('will-navigate',event=>event.preventDefault());
  win.webContents.session.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));
  win.loadFile(path.join(__dirname,'../dist/index.html'));
  win.on('close',event=>{if(!quitting){event.preventDefault();win.hide();}});
}
async function quitSafely() {
  if(quitting)return;
  try {if(backendReady)await request('/command','POST',{kind:'pause',payload:{}});}catch{}
  quitting=true;
  try {if(backendReady)await request('/shutdown','POST',{});}catch{}
  if(child&&child.exitCode===null) {
    await Promise.race([new Promise(resolve=>child.once('exit',resolve)),new Promise(resolve=>setTimeout(resolve,5000))]);
    if(child.exitCode===null) {
      const killer=spawn('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
      await new Promise(resolve=>{killer.once('exit',resolve);killer.once('error',resolve);});
    }
  }
  app.quit();
}
app.on('second-instance',()=>{if(win){win.show();win.focus();}});
app.on('before-quit',event=>{if(!quitting){event.preventDefault();quitSafely();}});
app.on('window-all-closed',()=>{});
app.whenReady().then(()=>{
  if(!single)return;
  fs.mkdirSync(app.getPath('userData'),{recursive:true});
  startBackend();
  createWindow();
  tray=new Tray(icon());
  tray.setToolTip('Kripto Terminali · Yerel araştırma ve sanal işlem');
  tray.setContextMenu(Menu.buildFromTemplate([
    {label:'Kripto Terminali’ni aç',click:()=>{win.show();win.focus();}},
    {label:'Yeni girişleri durdur',click:()=>request('/command','POST',{kind:'pause',payload:{}}).catch(()=>{})},
    {type:'separator'}, {label:'Motoru durdur ve çık',click:quitSafely}
  ]));
  tray.on('double-click',()=>{win.show();win.focus();});
  ipcMain.handle('engine-ready',()=>({ready:backendReady}));
  ipcMain.handle('request',async(_event,{route,method='GET',body})=>{
    const normalized=String(route||'').split('?')[0];
    if(!allowed.has(normalized)&&normalized!='/candles'&&!/^\/report\/[a-f0-9]{32}$/.test(normalized))throw new Error('İzin verilmeyen yerel arayüz.');
    if(!['GET','POST'].includes(method)||String(route).includes('://')||String(route).includes('..'))throw new Error('Geçersiz istek.');
    return request(route,method,body);
  });
  ipcMain.handle('save-credential',async(_event,value)=>{
    if(!value||!['Binance','Bybit'].includes(value.venue))throw new Error('Geçersiz borsa.');
    if(typeof value.key!=='string'||typeof value.secret!=='string'||value.key.length<8||value.secret.length<8||value.key.length>512||value.secret.length>512)throw new Error('Anahtar alanlarını kontrol edin.');
    const vault=readVault();
    vault.credentials={...(vault.credentials||{}),[value.venue]:{key:value.key,secret:value.secret,testnet:!!value.testnet}};
    writeVault(vault);
    return request('/credentials','POST',value);
  });
  ipcMain.handle('save-secret',async(_event,{kind,value})=>{
    if(!['ai','telegram'].includes(kind)||typeof value!=='string'||value.length>1024)throw new Error('Geçersiz anahtar türü.');
    const vault=readVault();vault[kind]=value;writeVault(vault);
    return request('/secrets','POST',{kind,value});
  });
  ipcMain.handle('window-action',(_event,action)=>{
    if(action==='minimize')win.minimize();
    else if(action==='maximize')win.isMaximized()?win.unmaximize():win.maximize();
    else if(action==='close')win.close();
    else if(action==='quit')return quitSafely();
  });
  ipcMain.handle('open-external',(_event,value)=>{
    const url=new URL(value);
    const hosts=['www.federalreserve.gov','www.sec.gov','www.bls.gov','www.ecb.europa.eu','www.whitehouse.gov','www.consilium.europa.eu','www.tradingview.com','developers.binance.com','bybit-exchange.github.io','www.aqr.com','arxiv.org','scikit-learn.org','www.davidhbailey.com'];
    if(url.protocol!=='https:'||!hosts.includes(url.hostname))throw new Error('Kaynak bağlantısı izin listesinde değil.');
    return shell.openExternal(url.href);
  });
});
