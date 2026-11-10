"""Portable Windows offline host; mutable data always lives beside the launcher."""
import sys,os,json,threading,time,logging,sqlite3,subprocess,shutil,ctypes
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parent))
import server
ROOT=Path(__file__).resolve().parent.parent
APP=ROOT/'app';DATA=ROOT/'data';EXPORTS=ROOT/'exports'
server.ROOT=APP

def alert(message):
 if os.name=='nt':ctypes.windll.user32.MessageBoxW(0,message,'鑽探工作台',0x10)
 else:print(message,file=sys.stderr)

class ProjectStore:
 """Project work is session memory only; only historical import outbox touches disk."""
 def __init__(self,folder):
  self.folder=Path(folder);self.folder.mkdir(exist_ok=True,parents=True);self.lock=threading.Lock();self.value=None
  self.outbox=self.folder/'history-pending.json'
 def read(self):
  with self.lock:return json.loads(json.dumps(self.value,ensure_ascii=False)) if self.value is not None else None
 def write(self,value):
  if not isinstance(value,dict) or not isinstance(value.get('project'),dict) or not isinstance(value.get('holes'),list) or not isinstance(value.get('items'),list) or not isinstance(value.get('history'),list):raise ValueError('專案格式不正確')
  raw=json.dumps(value,ensure_ascii=False,allow_nan=False)
  pending=value.get('desktopPendingHistory',[])
  if not isinstance(pending,list):raise ValueError('歷史單價暫存格式不正確')
  for record in pending:server.HistoryStore.validate(record)
  with self.lock:
   if pending:
    temporary=self.folder/'history-pending.tmp'
    try:
     with temporary.open('w',encoding='utf-8') as f:json.dump(pending,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
     os.replace(temporary,self.outbox)
    finally:temporary.unlink(missing_ok=True)
   else:self.outbox.unlink(missing_ok=True)
   self.value=json.loads(raw)
 def recover_history(self,store):
  if self.outbox.exists():
   pending=json.loads(self.outbox.read_text(encoding='utf-8'))
   if pending:store.merge(pending,store.read()['revision'])
   self.outbox.unlink()

class DesktopHandler(server.Handler):
 def log_message(self,format,*args):logging.info(format,*args)
 def allowed_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
 def do_GET(self):
  if not self.allowed_host():self.respond(403,{'error':'只接受本機工作台連線'});return
  route=self.path.split('?',1)[0]
  if route in ['/favicon.ico','/app-icon.ico']:
   raw=(ROOT/'drilling-workbench-blue.ico').read_bytes();self.send_response(200);self.send_header('Content-Type','image/x-icon');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
  if route=='/api/desktop-info':self.respond(200,{'app':'drilling-workbench-windows-v1','folder':str(ROOT)});return
  if route=='/api/desktop-session':
   self.server.last_client=time.monotonic();self.respond(200,{'quit':self.server.quit_requested});return
  if route=='/api/project':self.respond(200,{'project':self.server.projects.read()});return
  if route in ['/','/index.html']:
   value=self.server.projects.read();text=(APP/'index.html').read_text(encoding='utf-8').replace('第二版互動原型','Windows 單機正式版').replace('本機自動儲存','歷史單價自動儲存').replace('互動原型 v0.2<br>資料儲存在此瀏覽器<br>請匯出備份保存工作內容','Windows 單機版<br>歷史單價自動保存於本機<br>專案作業請匯出備份')
   text=text.replace('<title>','<link rel="icon" type="image/x-icon" href="/app-icon.ico"><title>',1)
   initial=json.dumps(value,ensure_ascii=True,allow_nan=False).replace('<','\\u003c')
   bootstrap='<script>window.desktopInitialProject='+initial+';const desktopMemory=new Map();const desktopStorage={getItem:k=>desktopMemory.get(String(k))??null,setItem:(k,v)=>desktopMemory.set(String(k),String(v)),removeItem:k=>desktopMemory.delete(String(k)),clear:()=>desktopMemory.clear(),key:i=>Array.from(desktopMemory.keys())[i]??null,get length(){return desktopMemory.size}};Object.defineProperty(window,"localStorage",{value:desktopStorage});const diskProject=window.desktopInitialProject;if(diskProject){localStorage.setItem("geotech-v1",JSON.stringify(diskProject));localStorage.setItem("geotech-history-outbox-v1",JSON.stringify(diskProject.desktopPendingHistory||[]))}</script>'
   text=text.replace("state=JSON.parse(localStorage.getItem('geotech-v1'))||seed()","state=window.desktopInitialProject||JSON.parse(localStorage.getItem('geotech-v1'))||seed()",1);text=text.replace("}catch{state=seed()}","}catch{state=window.desktopInitialProject||seed()}",1)
   position=text.index('<script');text=text[:position]+bootstrap+text[position:]
   adapter=(APP/'desktop-storage.js').read_text(encoding='utf-8');text=text.replace('</html>','<script>\n'+adapter+'\n</script></html>');raw=text.encode('utf-8')
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
  super().do_GET()
 def do_POST(self):
  if not self.allowed_host():self.respond(403,{'error':'只接受本機工作台連線'});return
  if self.path not in ['/api/project','/api/desktop-stop','/api/desktop-cancel-stop']:super().do_POST();return
  host=self.headers.get('Host');origin=self.headers.get('Origin')
  if self.headers.get('Sec-Fetch-Site')=='cross-site' or origin and origin!='http://'+host:self.respond(403,{'error':'不接受跨網站寫入'});return
  if self.path=='/api/desktop-cancel-stop':
   self.server.quit_requested=False;self.respond(200,{'cancelled':True});return
  if self.path=='/api/desktop-stop':
   self.respond(200,{'stopped':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
  try:
   if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('需要 JSON 格式')
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=128*1024*1024:raise ValueError('專案資料超過可接受大小')
   value=json.loads(self.rfile.read(length));self.server.projects.write(value);self.respond(200,{'saved':True,'storage':'session-memory'})
  except (ValueError,TypeError,OverflowError) as error:self.respond(400,{'error':str(error)})
  except OSError:self.respond(500,{'error':'無法寫入本機資料夾，請檢查磁碟空間和權限'})

def create_host(port=0,fresh_project=False):
 DATA.mkdir(exist_ok=True);EXPORTS.mkdir(exist_ok=True)
 probe=DATA/'.write-test';probe.write_bytes(b'');probe.unlink()
 projects=ProjectStore(DATA);projects.read()
 host=server.ThreadingHTTPServer(('127.0.0.1',port),DesktopHandler);host.store=server.HistoryStore(DATA/'history.sqlite3');host.projects=projects
 host.last_client=0;host.quit_requested=False
 try:projects.recover_history(host.store)
 except Exception:host.server_close();raise
 return host

def find_browser():
 candidates=[ROOT/'browser/chrome.exe']
 for base in [os.environ.get('PROGRAMFILES'),os.environ.get('PROGRAMFILES(X86)'),os.environ.get('LOCALAPPDATA')]:
  if base:candidates.extend([Path(base)/'Google/Chrome/Application/chrome.exe',Path(base)/'Microsoft/Edge/Application/msedge.exe'])
 for name in ['chrome.exe','msedge.exe']:
  found=shutil.which(name)
  if found:candidates.append(Path(found))
 return next((p for p in candidates if p.is_file()),None)

def verify_browser_runtime(browser):
 """Check only our bundled runtime. A system browser keeps its own installation."""
 if browser.resolve()!=(ROOT/'browser/chrome.exe').resolve():return
 manifest_path=ROOT/'release-manifest.json'
 if not manifest_path.exists():return
 manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
 files=manifest.get('browserEntryFiles',[])
 if not files:return
 import hashlib
 hashes={name.replace('\\','/'):digest for name,digest in manifest['files'].items()}
 for name in files:
  path=ROOT/'browser'/name
  if not path.is_file():raise RuntimeError('內附視窗元件缺少 '+name+'。請重新執行完整安裝檔修復；data 與匯出檔案會保留。')
  expected=hashes.get('browser/'+name)
  with path.open('rb') as source:actual=hashlib.file_digest(source,'sha256').hexdigest()
  if not expected or actual!=expected:raise RuntimeError('內附視窗元件損壞：'+name+'。請重新執行完整安裝檔修復。')

def open_browser(url,prefer_existing=True):
 from tray import focus_workbench
 if prefer_existing and focus_workbench(find_browser()):return
 browser=find_browser()
 if not browser:raise RuntimeError('找不到內附視窗元件，請重新安裝鑽探工作台。')
 profile=DATA/'browser-profile';profile.mkdir(exist_ok=True);default=profile/'Default';default.mkdir(exist_ok=True);preferences=default/'Preferences'
 if not preferences.exists():preferences.write_text(json.dumps({'download':{'default_directory':str(EXPORTS),'prompt_for_download':True},'browser':{'check_default_browser':False}}),encoding='utf-8')
 verify_browser_runtime(browser)
 from window_icons import start_window_branding
 process=subprocess.Popen([str(browser),'--app='+url,'--user-data-dir='+str(profile),'--no-first-run','--no-default-browser-check','--lang=zh-TW','--disable-background-networking','--disable-component-update','--disable-sync','--disable-domain-reliability','--no-pings','--metrics-recording-only','--disable-features=Translate,MediaRouter,OptimizationHints,OptimizationGuideModelDownloading,AutofillServerCommunication'],cwd=str(browser.parent),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 start_window_branding(ROOT,browser)
 return process

def existing_instance():
 path=DATA/'desktop-instance.json'
 try:
  details=json.loads(path.read_text(encoding='utf-8'));port=int(details['port']);url='http://127.0.0.1:'+str(port)
  with urlopen(url+'/api/desktop-info',timeout=1) as r:info=json.load(r)
  if info.get('app')=='drilling-workbench-windows-v1' and info.get('folder')==str(ROOT):return url
 except Exception:pass
 return None

def main():
 mutex=None
 try:
  DATA.mkdir(exist_ok=True)
  logging.basicConfig(filename=DATA/'desktop.log',level=logging.INFO,encoding='utf-8')
  # Folder-specific Windows named mutex prevents parallel hosts from racing the same ledger.
  if os.name=='nt':
   import hashlib
   name='Local\\DrillingWorkbench-'+hashlib.sha256(str(ROOT).lower().encode()).hexdigest()[:24]
   create=ctypes.windll.kernel32.CreateMutexW;create.restype=ctypes.c_void_p;mutex=create(None,False,name)
   if not mutex:raise RuntimeError('無法建立本機工作台啟動鎖')
   if ctypes.windll.kernel32.GetLastError()==183:
    for _ in range(30):
     url=existing_instance()
     if url:open_browser(url);return
     time.sleep(.2)
    raise RuntimeError('工作台啟動中或未正常回應，請稍後重試。')
  previous=existing_instance()
  if previous:open_browser(previous);return
  host=create_host(fresh_project=True);url='http://127.0.0.1:'+str(host.server_port)
  (DATA/'desktop-instance.json').write_text(json.dumps({'port':host.server_port}),encoding='utf-8')
  thread=threading.Thread(target=host.serve_forever,daemon=True);thread.start();open_browser(url,prefer_existing=False)
  host.serve_thread=thread
  from tray import TrayIcon
  def request_quit():
   host.quit_requested=True
   # Reopen the existing session so every exit path offers the backup choice.
   try:open_browser(url)
   except Exception:
    host.quit_requested=False;logging.exception('Tray exit prompt failed');alert('無法顯示結束提醒。程式尚未結束，請重新開啟工作台。')
  tray=TrayIcon(ROOT,lambda:open_browser(url),request_quit);tray.start()
  try:thread.join()
  finally:
   tray.close();host.server_close()
   from tray import close_workbench
   close_workbench(find_browser())
   (DATA/'desktop-instance.json').unlink(missing_ok=True)
 except Exception as error:
  logging.exception('Startup failed')
  if getattr(error,'winerror',None)==14001:message='內附視窗元件無法載入（Windows 14001）。請使用「鑽探工作台-網頁入口」以電腦原有瀏覽器開啟，或重新執行新版完整安裝檔修復。'
  else:message='無法啟動鑽探工作台：'+str(error)
  alert(message+'\n\n歷史單價及已匯出的專案備份未被刪除。詳細紀錄位於安裝資料夾 data/desktop.log。')
 finally:
  if mutex:
   close=ctypes.windll.kernel32.CloseHandle;close.argtypes=[ctypes.c_void_p];close(mutex)
if __name__=='__main__':main()
