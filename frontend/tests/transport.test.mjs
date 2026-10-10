import assert from 'node:assert/strict'
import test from 'node:test'
import {createTransport} from '../src/transport.ts'
const response=(status,data={})=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}})
test('403 never refreshes or loops',async()=>{
 let count=0
 const call=createTransport({getToken:()=>'',refresh:async()=>{count++},logout:()=>{},fetch:async()=>response(403,{detail:'仅系统管理员可进入'})})
 await assert.rejects(call('overview'),/仅系统管理员/);assert.equal(count,0)
})
test('concurrent expired calls share one refresh and replay exactly once',async()=>{
 let token='old',refreshes=0,calls=0
 const call=createTransport({getToken:()=>token,refresh:async()=>{refreshes++;await new Promise(r=>setTimeout(r,10));token='new'},logout:()=>{},fetch:async(url,init)=>{calls++;return init.headers.Authorization==='Bearer old'?response(401):response(200,{ok:true})}})
 const results=await Promise.all([call('overview'),call('tasks')]);assert.ok(results.every(x=>x.ok));assert.equal(refreshes,1);assert.equal(calls,4)
})
test('still rejected after refresh logs out without retry loop',async()=>{
 let calls=0,logout=0
 const call=createTransport({getToken:()=>'',refresh:async()=>{},logout:()=>{logout++},fetch:async()=>{calls++;return response(401)}})
 await assert.rejects(call('overview'),/过期/);assert.equal(calls,2);assert.equal(logout,1)
})
