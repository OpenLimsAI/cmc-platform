type Dependencies = {
 getToken:()=>string|null; refresh:()=>Promise<unknown>; logout:()=>void;
 fetch:(url:string,init:RequestInit)=>Promise<Response>;
}
export function createTransport(deps:Dependencies){
 let refreshing:Promise<unknown>|undefined
 let rejected=false
 const expire=()=>{if(!rejected){rejected=true;deps.logout()}throw new Error('登录已过期，请重新登录')}
 return async function request(path:string,init:RequestInit={}):Promise<any>{
  if(rejected)return expire()
  const send=(token:string|null)=>deps.fetch('/water/api/v1/'+path,{...init,headers:{'Content-Type':'application/json',...init.headers,Authorization:'Bearer '+token}})
  const token=deps.getToken()
  let res=await send(token)
  if(res.status===401){
   if(rejected)return expire()
   // Reuse an in-flight refresh, or a token already refreshed by another request.
   if(deps.getToken()===token){
    if(!refreshing)refreshing=deps.refresh().finally(()=>{refreshing=undefined})
    try{await refreshing}catch{return expire()}
   }
   if(rejected)return expire()
   res=await send(deps.getToken())
   if(res.status===401)return expire()
  }
  if(!res.ok){let body:any;try{body=await res.json()}catch{throw new Error(`服务暂不可用（HTTP ${res.status}），请重试`)}throw new Error(body.message||body.detail||'请求失败')}
  return path==='exports'?res.blob():res.json()
 }
}
