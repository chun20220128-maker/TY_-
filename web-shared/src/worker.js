const HEADERS={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','X-Robots-Tag':'noindex, nofollow','Content-Security-Policy':"frame-ancestors 'self'"};
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{...HEADERS,'Content-Type':'application/json; charset=utf-8'}});
const SCHEMA=[
 'CREATE TABLE IF NOT EXISTS history(identity TEXT PRIMARY KEY,project_code TEXT,year INTEGER,region TEXT,item TEXT,vendor TEXT,record TEXT NOT NULL)',
 'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value INTEGER NOT NULL,token TEXT)',
 'CREATE TABLE IF NOT EXISTS history_backups(revision INTEGER PRIMARY KEY,created_at TEXT NOT NULL,records TEXT NOT NULL)',
 "INSERT OR IGNORE INTO meta(key,value) VALUES('revision',0)"
];
export function identity(h){const code=(h.projectCode||'').trim();return JSON.stringify([code?'code':'name',code||h.project.trim(),...(code?[]:[String(h.year),h.region.trim()]),h.item.trim(),(h.vendor||'').trim(),h.unit.trim(),h.kind.trim()])}
const hex=bytes=>Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
async function digest(value){return hex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))}
async function authorized(request,env){
 const expected=env.ACCESS_TOKEN_SHA256;if(!/^[a-f0-9]{64}$/i.test(expected||''))return false;
 const header=request.headers.get('Authorization')||'';if(!/^Bearer [A-Za-z0-9_-]{43}$/.test(header))return false;
 const actual=await digest(header.slice(7));let difference=0;for(let i=0;i<64;i++)difference|=actual.charCodeAt(i)^expected.toLowerCase().charCodeAt(i);return difference===0;
}
const initialized=new WeakMap();
async function initialize(env,origin){
 if(initialized.has(env.DB))return initialized.get(env.DB);
 const promise=(async()=>{
  await env.DB.batch(SCHEMA.map(sql=>env.DB.prepare(sql)));
  const marker=await env.DB.prepare("SELECT value FROM meta WHERE key='seed_version'").first();if(marker)return;
  const response=await env.ASSETS.fetch(new Request(origin+'/protected/history-seed.json'));if(!response.ok)throw Error('Seed missing');
  const data=await response.json();const records=Array.isArray(data)?data:data.records;if(!Array.isArray(records))throw Error('Invalid seed');
  const rows=records.map(record=>({identity:identity(record),record}));
  await env.DB.batch([
   env.DB.prepare(`INSERT OR IGNORE INTO history SELECT json_extract(value,'$.identity'),json_extract(value,'$.record.projectCode'),json_extract(value,'$.record.year'),json_extract(value,'$.record.region'),json_extract(value,'$.record.item'),json_extract(value,'$.record.vendor'),json_extract(value,'$.record') FROM json_each(?) WHERE NOT EXISTS(SELECT 1 FROM meta WHERE key='seed_version')`).bind(JSON.stringify(rows)),
   env.DB.prepare("INSERT OR IGNORE INTO meta(key,value) VALUES('seed_version',1)")
  ]);
 })();initialized.set(env.DB,promise);try{await promise}catch(error){initialized.delete(env.DB);throw error}
}
async function read(db){
 const result=await db.batch([db.prepare('SELECT record FROM history ORDER BY rowid'),db.prepare("SELECT value FROM meta WHERE key='revision'")]);
 const records=result[0].results.map(r=>JSON.parse(r.record));return {revision:Number(result[1].results[0].value),records,projectCount:new Set(records.map(h=>h.projectCode||h.project)).size,storage:'cloudflare-d1'};
}
class InputError extends Error{}
function validate(record){
 if(!record||typeof record!=='object'||Array.isArray(record))throw new InputError('歷史單價格式不正確');
 for(const key of ['project','region','item','unit','kind'])if(typeof record[key]!=='string'||!record[key].trim()||record[key].length>4000)throw new InputError('歷史欄位缺少或過長：'+key);
 for(const key of ['id','projectCode','vendor'])if(record[key]!==undefined&&(typeof record[key]!=='string'||record[key].length>4000))throw new InputError('歷史欄位格式不正確：'+key);
 if(!Number.isInteger(record.year)||record.year<1000||record.year>9999)throw new InputError('年度不正確');
 if(typeof record.price!=='number'||!Number.isFinite(record.price)||record.price<0||record.price>1e15)throw new InputError('單價不正確');
 if(record.project.includes('示範')&&record.project.includes('非真實'))throw new InputError('不匯入非真實示範單價');
}
async function importHistory(env,body){
 if(!Number.isInteger(body?.revision)||!Array.isArray(body?.records)||body.records.length>5000)return json({error:'匯入格式或筆數不正確；請分批匯入。'},400);
 const current=await read(env.DB);if(body.revision!==current.revision)return json({error:'其他工程師已更新共用單價，本次未寫入。請重新載入共用單價後再確認匯入。'},409);
 const previous=new Map(current.records.map(h=>[identity(h),h])),seen=new Set(),rows=[],now=new Date().toISOString();const counts={added:0,updated:0,unchanged:0};
 for(const input of body.records){
  validate(input);const key=identity(input);if(seen.has(key))return json({error:'同批資料含重複工項'},400);seen.add(key);
  const old=previous.get(key),record={};for(const name of ['project','projectCode','year','region','item','unit','kind','vendor','price'])record[name]=input[name]??'';
  if(old&&['project','projectCode','year','region','item','unit','kind','vendor','price'].every(k=>(old[k]??'')===(record[k]??''))){counts.unchanged++;continue}
  record.id=old?.id||'history-'+(await digest(key)).slice(0,24);record.importedAt=old?.importedAt||now;if(old)record.updatedAt=now;
  rows.push({identity:key,record});counts[old?'updated':'added']++;
 }
 if(!rows.length)return json({...current,...counts});
 const nonce=crypto.randomUUID();
 const results=await env.DB.batch([
  env.DB.prepare("UPDATE meta SET value=value+1,token=? WHERE key='revision' AND value=?").bind(nonce,current.revision),
  env.DB.prepare("INSERT OR REPLACE INTO history_backups SELECT ?,?,? WHERE EXISTS(SELECT 1 FROM meta WHERE key='revision' AND token=?)").bind(current.revision,now,JSON.stringify(current.records),nonce),
  env.DB.prepare(`INSERT INTO history SELECT json_extract(value,'$.identity'),json_extract(value,'$.record.projectCode'),json_extract(value,'$.record.year'),json_extract(value,'$.record.region'),json_extract(value,'$.record.item'),json_extract(value,'$.record.vendor'),json_extract(value,'$.record') FROM json_each(?) WHERE EXISTS(SELECT 1 FROM meta WHERE key='revision' AND token=?) ON CONFLICT(identity) DO UPDATE SET project_code=excluded.project_code,year=excluded.year,region=excluded.region,item=excluded.item,vendor=excluded.vendor,record=excluded.record`).bind(JSON.stringify(rows),nonce),
  env.DB.prepare("DELETE FROM history_backups WHERE revision < ? AND EXISTS(SELECT 1 FROM meta WHERE key='revision' AND token=?)").bind(current.revision-29,nonce),
  env.DB.prepare('SELECT record FROM history ORDER BY rowid'),env.DB.prepare("SELECT value FROM meta WHERE key='revision'")
 ]);
 if(!results[0].meta.changes)return json({error:'共用單價剛被其他工程師更新，本次未寫入，請重新載入後確認。'},409);
 const records=results[4].results.map(r=>JSON.parse(r.record));return json({revision:Number(results[5].results[0].value),records,projectCount:new Set(records.map(h=>h.projectCode||h.project)).size,storage:'cloudflare-d1',...counts});
}
export default {async fetch(request,env){
 const url=new URL(request.url),path=url.pathname;
 // Old Pages deployments must not keep an old key valid after production rotation.
 if(url.hostname.endsWith('.pages.dev')&&url.hostname.split('.').length>3){const production=url.hostname.split('.').slice(-3).join('.');if(path.startsWith('/api/'))return json({error:'請使用公司的固定專用連結。'},403);return new Response(null,{status:302,headers:{...HEADERS,Location:'https://'+production+url.pathname+url.search}})}
 if(request.method==='GET'&&(path==='/'||path==='/index.html'||path==='/favicon.ico'||path==='/robots.txt')){
  const response=await env.ASSETS.fetch(new Request(url.origin+(path==='/index.html'?'/':path)));return new Response(response.body,{status:response.status,headers:{...Object.fromEntries(response.headers),...HEADERS}});
 }
 if(request.method==='GET'&&path==='/setup'&&!/^[a-f0-9]{64}$/i.test(env.ACCESS_TOKEN_SHA256||'')){const response=await env.ASSETS.fetch(new Request(url.origin+'/protected/setup.bundle'));return new Response(response.body,{status:response.status,headers:{...Object.fromEntries(response.headers),...HEADERS,'Content-Type':'text/html; charset=utf-8'}})}
 if(!path.startsWith('/api/'))return json({error:'找不到此頁面'},404);
 if(!await authorized(request,env))return json({error:'請使用管理者提供的有效專用連結。'},401);
 const origin=request.headers.get('Origin');if(origin&&origin!==url.origin)return json({error:'不接受跨網站操作'},403);
 if(path==='/api/app'&&request.method==='GET'){
  if(!env.DB)return json({error:'管理者尚未完成共用資料庫設定，請稍後再試。'},503);
  const response=await env.ASSETS.fetch(new Request(url.origin+'/protected/app.bundle'));return new Response(response.body,{status:response.status,headers:{...Object.fromEntries(response.headers),...HEADERS,'Content-Type':'text/html; charset=utf-8'}});
 }
 if(!env.DB)return json({error:'共用資料庫尚未就緒，請稍後再試。'},503);
 try{
  await initialize(env,url.origin);
  if(path==='/api/history'&&request.method==='GET')return json(await read(env.DB));
  if(path==='/api/history/import'&&request.method==='POST'){
   if(!request.headers.get('Content-Type')?.startsWith('application/json'))return json({error:'需要 JSON 格式'},415);
   const text=await request.text();if(new TextEncoder().encode(text).length>2*1024*1024)return json({error:'檔案過大，請分批匯入。'},413);
   let data;try{data=JSON.parse(text)}catch{return json({error:'JSON 格式不正確'},400)}
   try{return await importHistory(env,data)}catch(error){if(error instanceof InputError)return json({error:error.message},400);throw error}
  }
  return json({error:'找不到此功能'},404);
 }catch(error){console.error('Shared history unavailable:',error.message);return json({error:'共用歷史單價暫時無法連線；目前專案仍保留在畫面中，請先匯出備份。'},503)}
}};
