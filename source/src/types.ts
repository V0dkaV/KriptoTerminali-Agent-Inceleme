export type Row = Record<string, any>;
export interface TerminalBridge {
  ready(): Promise<{ready:boolean}>;
  request<T=any>(route:string,method?:string,body?:unknown):Promise<T>;
  saveCredential(value:{venue:string;key:string;secret:string;testnet:boolean}):Promise<Row>;
  saveSecret(kind:string,value:string):Promise<Row>;
  windowAction(action:string):Promise<void>;
  openExternal(url:string):Promise<void>;
}
declare global { interface Window { terminal:TerminalBridge } }
export type Candle = {time:number;open:number;high:number;low:number;close:number;volume:number};
export interface ExecutionState {
  entry_gate?:{code:string;blocked:boolean;label:string;message:string};
  signal_intervals:string[];heartbeat_age:number|null;
  training:{queued:number;running:boolean;completed:number;last_duration:number|null};
  analysis:{completed:number;expected:number;latest_at:number;oldest_at:number};
  reasons:{code:string;label:string;count:number}[];
  approved:number;positions:number;capital:number;last_dispatch_at:number|null;model_note:string;
}
export interface Snapshot {
  mode:string;running:boolean;halt:string;timestamp:number;version:string;source_status:string;
  metrics:Row;positions:Row[];closed:Row[];groups:Row[];markets:Row[];curve:Row[];
  strategies:Row[];news:Row[];news_sources:Row[];connections:Row[];jobs:Row[];reports:Row[];
  settings:Row;audit:Row[];live_gate:Row;paper_days:number;allocation:Row[];
  decisions:Row[];learning:Row[];session:Row;
  local_ai:Row;
  knowledge:Row;
  risk_profiles:Record<string,Row>;universe:Row;
  execution?:ExecutionState;
}
