import {test} from 'node:test'
import assert from 'node:assert/strict'
import {createTransport} from '../src/transport.ts'
const response=status=>new Response(JSON.stringify({ok:true}),{status})
test('concurrent expired requests share refresh and retry with new token',async()=>{
 let token='old',refreshes=0,logouts=0
 const api=createTransport({getToken:()=>token,refresh:async()=>{refreshes++;await new Promise(r=>setTimeout(r,5));token='new'},logout:()=>logouts++,fetch:async(_,i)=>response(i.headers.Authorization==='Bearer old'?401:200)})
 await Promise.all([api('context'),api('filters'),api('overview')]);assert.equal(refreshes,1);assert.equal(logouts,0)
})
test('a rejected refreshed token closes session once and stops new requests',async()=>{
 let token='old',refreshes=0,logouts=0,calls=0
 const api=createTransport({getToken:()=>token,refresh:async()=>{refreshes++;token='new'},logout:()=>logouts++,fetch:async()=>{calls++;return response(401)}})
 await Promise.allSettled([api('context'),api('filters')]);const before=calls;await assert.rejects(api('overview'),/重新登录/);assert.equal(calls,before);assert.equal(refreshes,1);assert.equal(logouts,1)
})
test('refresh failure closes session; forbidden access never refreshes',async()=>{
 let refreshes=0,logouts=0
 const api=createTransport({getToken:()=> 'old',refresh:async()=>{refreshes++;throw Error()},logout:()=>logouts++,fetch:async()=>response(401)})
 await assert.rejects(api('context'));assert.equal(logouts,1)
 const denied=createTransport({getToken:()=> 'old',refresh:async()=>{refreshes++},logout:()=>logouts++,fetch:async()=>new Response(JSON.stringify({detail:'没有导出权限'}),{status:403})})
 await assert.rejects(denied('exports'),/没有导出权限/);assert.equal(refreshes,1)
})
