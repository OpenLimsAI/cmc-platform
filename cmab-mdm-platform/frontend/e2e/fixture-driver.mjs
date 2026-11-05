/** Node helpers for the supported CUA adapter. No browser launcher, HTTP client,
 * session injection, subprocess or arbitrary fixture command is exposed. */
import * as fs from 'node:fs/promises';
import * as path from 'node:path';
import * as crypto from 'node:crypto';
import {setTimeout as delay} from 'node:timers/promises';

const actions=new Set(['snapshot','fault-next-link','stop-mdm','start-mdm','restart-apps']);
function checkedDirectory(directory) {
  const resolved=path.resolve(directory);
  if (!/^mdm-e2e-[a-z0-9][a-z0-9-]{0,39}$/.test(path.basename(resolved)) || path.basename(path.dirname(resolved))!=='.local-e2e') throw Error('Not an owned local E2E directory');
  return resolved;
}

export async function createFixtureHandoff(directory) {
  const root=checkedDirectory(directory);
  const fixture={syntheticOnly:true,users:Object.fromEntries(['signer','other'].map(k=>[k,{username:'e2e.'+k,password:crypto.randomBytes(24).toString('hex')}]))};
  const key=await fs.readFile(path.join(root,'fixture-public.pem'));
  const sealed=crypto.publicEncrypt({key,padding:crypto.constants.RSA_PKCS1_OAEP_PADDING,oaepHash:'sha256'},Buffer.from(JSON.stringify(fixture)));
  await fs.writeFile(path.join(root,'fixture.sealed'),sealed,{flag:'wx'});
  return fixture; // Keep only in the CUA driver's memory; never print it.
}

export function createController(directory) {
  const root=checkedDirectory(directory);
  return async(action,fields={})=>{
    if (!actions.has(action)) throw Error('Unrecognized fixture control');
    await fs.mkdir(path.join(root,'control'),{recursive:true});
    const id=crypto.randomBytes(16).toString('hex');
    const pending=path.join(root,'control',id+'.pending');
    await fs.writeFile(pending,JSON.stringify({...fields,id,action}),{flag:'wx'});
    await fs.rename(pending,path.join(root,'control/request.json'));
    const response=path.join(root,'control',id+'.json');
    const deadline=Date.now()+45000;
    while(Date.now()<deadline) {
      let text;
      try {text=await fs.readFile(response,'utf8');}
      catch(error) {if(error.code!=='ENOENT') throw error;}
      if(text) {
        let value;
        try {value=JSON.parse(text);} catch {await delay(100);continue;}
        if(value.id!==id || value.status!=='passed') throw Error('Owned fixture control failed; do not retry blindly');
        return value.result;
      }
      await delay(100); // Non-UI, bounded wait for the CLI host's receipt.
    }
    throw Error('Fixture control outcome uncertain; inspect before repeating');
  };
}

export function createCapture(directory,prefix='') {
  const root=checkedDirectory(directory);
  if (!/^[a-z0-9-]*$/.test(prefix)) throw Error('Unexpected screenshot prefix');
  return async(tab,name)=>{
    if (!/^[a-z0-9-]+\.(jpg|png)$/.test(name)) throw Error('Unexpected screenshot name');
    const bytes=await tab.screenshot({fullPage:false});
    const file=prefix+name.replace(/\.(jpg|png)$/,bytes[0]===137?'.png':'.jpg');
    await fs.writeFile(path.join(root,'screenshots',file),bytes,{flag:'wx'});
    const row={file,time_utc:new Date().toISOString(),sha256:crypto.createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length,synthetic_only:true,casdoor:'v4.25.0'};
    await fs.appendFile(path.join(root,'screenshots.jsonl'),JSON.stringify(row)+'\n');
  };
}

export async function saveCase(directory,record) {
  await fs.appendFile(path.join(checkedDirectory(directory),'case-results.jsonl'),JSON.stringify({...record,time_utc:new Date().toISOString()})+'\n');
}

export async function finishRun(directory,result) {
  await fs.writeFile(path.join(checkedDirectory(directory),'browser-result.json'),JSON.stringify({...result,time_utc:new Date().toISOString(),synthetic_only:true},null,2),{flag:'wx'});
}
