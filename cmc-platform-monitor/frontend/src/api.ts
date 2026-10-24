import {createTransport} from './transport'
import {getStoredToken,mdmRefresh,clearSession} from './shared/cmabSession'
import {demoSnapshot,demoHistory} from './demo'
import type {Snapshot,History} from './types'
export const demo=import.meta.env.VITE_DEMO_MODE==='true'
const login=()=>{clearSession();location.assign('/login?redirect='+encodeURIComponent('/ops/'))}
export const request=createTransport({getToken:getStoredToken,refresh:mdmRefresh,logout:login,fetch:window.fetch.bind(window)})
export const loadOverview=()=>demo?Promise.resolve(demoSnapshot()):request<Snapshot>('overview')
export const loadHistory=(key:string,snapshotId:string,days=7,offset=0)=>demo?Promise.resolve(demoHistory(key,days,offset)):request<History>(`tasks/${encodeURIComponent(key)}/runs?snapshot_id=${encodeURIComponent(snapshotId)}&days=${days}&offset=${offset}`)
export async function refreshOverview():Promise<Snapshot>{
 if(demo)return demoSnapshot()
 const update=await request<{update_id:string}>('refresh',{method:'POST'})
 const deadline=Date.now()+45000
 while(Date.now()<deadline){
  await new Promise(resolve=>setTimeout(resolve,1000))
  const status=await request<{status:string;snapshot_id:string|null}>(`updates/${encodeURIComponent(update.update_id)}`)
  if(status.status==='done'&&status.snapshot_id)return request<Snapshot>('overview?snapshot_id='+encodeURIComponent(status.snapshot_id))
 }
 throw new Error('更新尚未完成，当前状态未核实。稍后点击更新重试。')
}
