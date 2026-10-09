import { getStoredToken, mdmRefresh, clearSession } from './shared/cmabSession'
export function loginRedirect(){ location.href='/login?redirect='+encodeURIComponent(location.pathname+location.search) }
import { createTransport } from './transport'
export const api=createTransport({getToken:getStoredToken,refresh:mdmRefresh,logout:()=>{clearSession();loginRedirect()},fetch:(url,init)=>fetch(url,init)})
export function query(filter:Record<string,any>){ const params=new URLSearchParams();Object.entries(filter).forEach(([k,v])=>{if(Array.isArray(v))v.forEach(x=>params.append(k,x));else if(v!==undefined&&v!==null)params.set(k,v)});return params.toString() }
