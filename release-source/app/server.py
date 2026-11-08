"""Private workbench server. Run: python3 server.py (stdlib only)."""
import argparse,json,math,sqlite3,hashlib,threading
from urllib.parse import unquote,quote
from pathlib import Path
from datetime import datetime,timezone
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler

ROOT=Path(__file__).resolve().parent
class Conflict(Exception): pass
class HistoryStore:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
  with self.connect() as db:
   db.executescript('CREATE TABLE IF NOT EXISTS history(identity TEXT PRIMARY KEY, project_code TEXT, year INTEGER, region TEXT, item TEXT, vendor TEXT, record TEXT NOT NULL); CREATE INDEX IF NOT EXISTS history_project ON history(project_code); CREATE INDEX IF NOT EXISTS history_region ON history(region); CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT); INSERT OR IGNORE INTO meta VALUES(\'revision\',\'0\');')
  seeds=json.loads((ROOT/'data/history-seed.json').read_text(encoding='utf-8'))
  with self.lock,self.connect() as db:
   if not db.execute("SELECT 1 FROM meta WHERE key='seed-v1'").fetchone():
    self._merge(db,seeds);db.execute("INSERT INTO meta VALUES('seed-v1',?)",(datetime.now(timezone.utc).isoformat(),));db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")
  self.remove_demo_records()
  self.backup()
 def remove_demo_records(self):
  with self.lock,self.connect() as db:
   keys=[key for key,record in db.execute('SELECT identity,record FROM history') if self.is_demo(json.loads(record))]
   if keys:
    db.executemany('DELETE FROM history WHERE identity=?',[(key,) for key in keys]);db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")
  return len(keys)
 @staticmethod
 def is_demo(h):
  name=str(h.get('project',''));return '示範' in name and '非真實報價' in name
 def connect(self):
  db=sqlite3.connect(self.path,timeout=15);db.execute('PRAGMA journal_mode=WAL');return db
 @staticmethod
 def identity(h):
  code=h.get('projectCode','').strip();return json.dumps(['code' if code else 'name',code or h['project'].strip(),*([] if code else [str(h['year']),h['region'].strip()]),h['item'].strip(),h.get('vendor','').strip(),h['unit'].strip(),h['kind'].strip()],ensure_ascii=False,separators=(',',':'))
 @staticmethod
 def validate(h):
  if not isinstance(h,dict):raise ValueError('歷史單價格式不正確')
  for k in ['project','region','item','unit','kind']:
   if not isinstance(h.get(k),str) or not h[k].strip() or len(h[k])>4000:raise ValueError('歷史欄位缺少或過長：'+k)
  for k in ['id','projectCode','vendor']:
   if not isinstance(h.get(k,''),str) or len(h.get(k,''))>4000:raise ValueError('歷史欄位格式不正確：'+k)
  if not isinstance(h.get('year'),int) or isinstance(h['year'],bool) or not 1000<=h['year']<=9999:raise ValueError('年度不正確')
  if not isinstance(h.get('price'),(int,float)) or isinstance(h['price'],bool) or not math.isfinite(h['price']) or h['price']<0:raise ValueError('單價不正確')
  json.dumps(h,allow_nan=False)
 def _merge(self,db,records):
  seen=set();counts={'added':0,'updated':0,'unchanged':0}
  for record in records:
   self.validate(record)
   if self.is_demo(record):raise ValueError('非真實報價示範案件不再匯入歷史單價資料庫')
   h=dict(record);key=self.identity(h)
   if key in seen:raise ValueError('同批資料有重複工項')
   seen.add(key);old=db.execute('SELECT record FROM history WHERE identity=?',(key,)).fetchone()
   if old:
    previous=json.loads(old[0]);h['id']=previous['id']
    compare=['project','projectCode','year','region','item','unit','kind','vendor','price']
    if all(previous.get(k,'')==h.get(k,'') for k in compare):counts['unchanged']+=1;continue
    h['importedAt']=previous.get('importedAt',h.get('importedAt'));h['updatedAt']=datetime.now(timezone.utc).isoformat()
   else:h['id']='history-'+hashlib.sha256(key.encode()).hexdigest()[:24]
   db.execute('INSERT INTO history VALUES(?,?,?,?,?,?,?) ON CONFLICT(identity) DO UPDATE SET project_code=excluded.project_code,year=excluded.year,region=excluded.region,item=excluded.item,vendor=excluded.vendor,record=excluded.record',(key,h.get('projectCode',''),h['year'],h['region'],h['item'],h.get('vendor',''),json.dumps(h,ensure_ascii=False,allow_nan=False)))
   counts['updated' if old else 'added']+=1
  return counts
 def read(self):
  with self.lock,self.connect() as db:return self._read(db)
 def _read(self,db):
  rows=[json.loads(x[0]) for x in db.execute('SELECT record FROM history ORDER BY rowid')];return {'revision':int(db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0]),'records':rows,'projectCount':len({h.get('projectCode') or h['project'] for h in rows}),'storage':'sqlite'}
 def merge(self,records,revision):
  if not isinstance(records,list) or len(records)>100000:raise ValueError('資料筆數不正確')
  if not isinstance(revision,int):raise ValueError('缺少資料版本')
  with self.lock,self.connect() as db:
   db.execute('BEGIN IMMEDIATE')
   actual=int(db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])
   if revision!=actual:raise Conflict('資料庫已由其他視窗更新，請重新載入後匯入；本次未寫入')
   counts=self._merge(db,records)
   if counts['added']+counts['updated']:db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")
   result={**self._read(db),**counts}
  self.backup();return result
 def backup(self):
  with self.lock,self.connect() as db:
   with sqlite3.connect(self.path.with_name(self.path.stem+'-backup.sqlite3')) as dest:db.backup(dest)

class Handler(BaseHTTPRequestHandler):
 def respond(self,status,data):
  payload=json.dumps(data,ensure_ascii=False,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 def do_GET(self):
  route=self.path.split('?',1)[0]
  if route=='/api/history':self.respond(200,self.server.store.read());return
  if route.startswith('/data/contract-templates/'):
   name=unquote(route[len('/data/contract-templates/'):]);manifest=json.loads((ROOT/'data/contract-templates.json').read_text(encoding='utf-8'))
   if name not in {item['name'] for item in manifest}:self.respond(404,{'error':'Not found'});return
   path=ROOT/'data/contract-templates'/name
   if not path.is_file():self.respond(404,{'error':'Not found'});return
   self.send_response(200);self.send_header('Content-Type','application/vnd.openxmlformats-officedocument.wordprocessingml.document' if name.endswith('.docx') else 'application/msword');self.send_header('Content-Length',str(path.stat().st_size));self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(name));self.end_headers()
   with path.open('rb') as document:
    while chunk:=document.read(1024*1024):self.wfile.write(chunk)
   return
  if route not in ['/','/index.html']:self.respond(404,{'error':'Not found'});return
  contents=(ROOT/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-cache');self.send_header('Content-Length',str(len(contents)));self.end_headers();self.wfile.write(contents)
 def do_POST(self):
  if self.path!='/api/history/import':self.respond(404,{'error':'Not found'});return
  origin=self.headers.get('Origin');host=self.headers.get('Host','')
  if self.headers.get('Sec-Fetch-Site')=='cross-site' or origin and origin not in ['http://'+host,'https://'+host]:self.respond(403,{'error':'不接受跨網站寫入'});return
  if self.headers.get('Content-Type','').split(';')[0]!='application/json':self.respond(415,{'error':'需要 JSON 格式'});return
  try:
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=32*1024*1024:raise ValueError('檔案大小不正確')
   data=json.loads(self.rfile.read(size));self.respond(200,self.server.store.merge(data.get('records'),data.get('revision')))
  except Conflict as e:self.respond(409,{'error':str(e)})
  except (ValueError,TypeError,AttributeError,OverflowError) as e:self.respond(400,{'error':str(e)})
  except (OSError,sqlite3.Error):self.respond(500,{'error':'資料庫寫入失敗，請保留備份後重試'})

def main():
 p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8000);p.add_argument('--db',default=str(ROOT/'data/history.sqlite3'));p.add_argument('--init-only',action='store_true');args=p.parse_args();store=HistoryStore(args.db)
 if args.init_only:print(json.dumps({k:v for k,v in store.read().items() if k!='records'},ensure_ascii=False));return
 server=ThreadingHTTPServer((args.host,args.port),Handler);server.store=store;print('Private workbench server ready',flush=True);server.serve_forever()
if __name__=='__main__':main()
