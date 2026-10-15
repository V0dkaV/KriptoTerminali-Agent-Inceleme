const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('terminal',{
  ready:()=>ipcRenderer.invoke('engine-ready'),
  request:(route,method='GET',body)=>ipcRenderer.invoke('request',{route,method,body}),
  saveCredential:value=>ipcRenderer.invoke('save-credential',value),
  saveSecret:(kind,value)=>ipcRenderer.invoke('save-secret',{kind,value}),
  windowAction:action=>ipcRenderer.invoke('window-action',action),
  openExternal:url=>ipcRenderer.invoke('open-external',url)
});
