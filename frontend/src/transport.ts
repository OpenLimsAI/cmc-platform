type Dependencies={getToken:()=>string|null;refresh:()=>Promise<unknown>;logout:()=>void;fetch:typeof fetch}
export function createTransport(deps:Dependencies){
 let refreshPromise:Promise<unknown>|undefined
 return async function request<T>(path:string,init:RequestInit={}):Promise<T>{
  const send=()=>deps.fetch('/ops/api/v1/'+path,{...init,credentials:'same-origin',headers:{'Content-Type':'application/json',...init.headers,Authorization:'Bearer '+deps.getToken()}})
  const firstToken=deps.getToken();let response=await send()
  if(response.status===401){
   if(deps.getToken()===firstToken){
    if(!refreshPromise)refreshPromise=deps.refresh().finally(()=>{refreshPromise=undefined})
    try{await refreshPromise}catch{deps.logout();throw new Error('登录已过期，请重新登录')}
   }
   response=await send()
   if(response.status===401){deps.logout();throw new Error('登录已过期，请重新登录')}
  }
  const body=await response.json().catch(()=>null)
  if(!response.ok)throw new Error(body?.message||body?.detail||`服务暂不可用（${response.status}）`)
  return body as T
 }
}
