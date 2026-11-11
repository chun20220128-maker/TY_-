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
const COOKIE='__Host-workbench_session';
const AUTH_SCHEMA=["CREATE TABLE IF NOT EXISTS web_sessions(token_hash TEXT PRIMARY KEY,credential_hash TEXT NOT NULL,expires INTEGER NOT NULL)","CREATE TABLE IF NOT EXISTS web_login_limits(client TEXT PRIMARY KEY,attempts INTEGER NOT NULL,reset_at INTEGER NOT NULL)"];
async function authDB(env){if(!env.DB)throw Error('Missing DB');await env.DB.batch(AUTH_SCHEMA.map(s=>env.DB.prepare(s)))}
function configured(env){return typeof env.LOGIN_USERNAME==='string'&&env.LOGIN_USERNAME.length>0&&typeof env.LOGIN_PASSWORD==='string'&&env.LOGIN_PASSWORD.length>=12}
async function credentialHash(env){return digest(JSON.stringify([env.LOGIN_USERNAME,env.LOGIN_PASSWORD]))}
function sessionToken(request){return request.headers.get('Cookie')?.split(';').map(x=>x.trim()).find(x=>x.startsWith(COOKIE+'='))?.slice(COOKIE.length+1)||''}
function cookie(value,age){return COOKIE+'='+value+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age='+age}
async function authorized(request,env){
 if(!configured(env)||!env.DB)return false;const token=sessionToken(request);if(!/^[a-f0-9]{64}$/.test(token))return false;
 await authDB(env);const row=await env.DB.prepare('SELECT credential_hash,expires FROM web_sessions WHERE token_hash=?').bind(await digest(token)).first();return !!row&&row.expires>Date.now()&&row.credential_hash===await credentialHash(env);
}
async function login(request,env){
 if(!configured(env)||!env.DB)return json({error:'管理者尚未完成登入設定。'},503);
 if(!request.headers.get('Content-Type')?.startsWith('application/json'))return json({error:'請使用登入表單。'},415);
 const raw=await request.text();if(raw.length>4096)return json({error:'輸入過長。'},400);let body;try{body=JSON.parse(raw)}catch{return json({error:'輸入格式錯誤。'},400)}
 if(typeof body.username!=='string'||typeof body.password!=='string')return json({error:'請輸入帳號及密碼。'},400);
 await authDB(env);const now=Date.now(),client=await digest(request.headers.get('CF-Connecting-IP')||'unknown');
 const rate=await env.DB.prepare('INSERT INTO web_login_limits(client,attempts,reset_at) VALUES(?,1,?) ON CONFLICT(client) DO UPDATE SET attempts=CASE WHEN reset_at<=? THEN 1 ELSE attempts+1 END,reset_at=CASE WHEN reset_at<=? THEN excluded.reset_at ELSE reset_at END RETURNING attempts').bind(client,now+900000,now,now).first();
 if(rate.attempts>10)return new Response(JSON.stringify({error:'登入嘗試過多，請於15分鐘後再試。'}),{status:429,headers:{...HEADERS,'Content-Type':'application/json','Retry-After':'900'}});
 const expected=await credentialHash(env),actual=await digest(JSON.stringify([body.username,body.password]));let diff=0;for(let i=0;i<64;i++)diff|=expected.charCodeAt(i)^actual.charCodeAt(i);
 if(diff)return json({error:'帳號或密碼不正確。'},401);
 const token=hex(crypto.getRandomValues(new Uint8Array(32)));
 await env.DB.batch([env.DB.prepare('DELETE FROM web_sessions WHERE expires<=?').bind(now),env.DB.prepare('DELETE FROM web_login_limits WHERE reset_at<=?').bind(now),env.DB.prepare('INSERT INTO web_sessions(token_hash,credential_hash,expires) VALUES(?,?,?)').bind(await digest(token),expected,now+28800000),env.DB.prepare('DELETE FROM web_login_limits WHERE client=?').bind(client)]);
 return new Response(JSON.stringify({ok:true}),{headers:{...HEADERS,'Content-Type':'application/json','Set-Cookie':cookie(token,28800)}});
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
export default {async fetch(request,env){
 const url=new URL(request.url),path=url.pathname;
 // Old Pages deployments must not keep an old key valid after production rotation.
 if(url.hostname.endsWith('.pages.dev')&&url.hostname.split('.').length>3){const production=url.hostname.split('.').slice(-3).join('.');if(path.startsWith('/api/'))return json({error:'請使用公司的固定專用連結。'},403);return new Response(null,{status:302,headers:{...HEADERS,Location:'https://'+production+url.pathname+url.search}})}
 if(request.method==='GET'&&(path==='/'||path==='/index.html'||path==='/favicon.ico'||path==='/robots.txt')){
  const response=await env.ASSETS.fetch(new Request(url.origin+(path==='/index.html'?'/':path)));return new Response(response.body,{status:response.status,headers:{...Object.fromEntries(response.headers),...HEADERS}});
 }
 if(!path.startsWith('/api/'))return json({error:'找不到此頁面'},404);
 const origin=request.headers.get('Origin');if(origin&&origin!==url.origin)return json({error:'不接受跨網站操作'},403);
 try{
 if(path==='/api/login'&&request.method==='POST'){
  if(origin!==url.origin)return json({error:'請從本站登入。'},403);return await login(request,env);
 }
 if(path==='/api/logout'&&request.method==='POST'){
  if(origin!==url.origin)return json({error:'不接受跨網站操作'},403);
  if(env.DB){await authDB(env);await env.DB.prepare('DELETE FROM web_sessions WHERE token_hash=?').bind(await digest(sessionToken(request))).run()}
  return new Response(JSON.stringify({ok:true}),{headers:{...HEADERS,'Content-Type':'application/json','Set-Cookie':cookie('',0)}});
 }
 if(!await authorized(request,env))return json({error:'請先登入鑽探工作台。'},401);
 if(path==='/api/app'&&request.method==='GET'){
  if(!env.DB)return json({error:'管理者尚未完成共用資料庫設定，請稍後再試。'},503);
  const response=await env.ASSETS.fetch(new Request(url.origin+'/protected/app.bundle'));return new Response(response.body,{status:response.status,headers:{...Object.fromEntries(response.headers),...HEADERS,'Content-Type':'text/html; charset=utf-8'}});
 }
 if(!env.DB)return json({error:'共用資料庫尚未就緒，請稍後再試。'},503);
  await initialize(env,url.origin);
  if(path==='/api/history'&&request.method==='GET')return json(await read(env.DB));
  if(path==='/api/history/import')return json({error:'網頁版歷史單價僅供查閱，不開放匯入。'},403);
  return json({error:'找不到此功能'},404);
 }catch(error){console.error('Shared history unavailable:',error.message);return json({error:'共用歷史單價暫時無法連線；目前專案仍保留在畫面中，請先匯出備份。'},503)}
}};
