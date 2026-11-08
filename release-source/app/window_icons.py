"""Windows icon, taskbar identity, and shortcut branding (stdlib/Win32 only)."""
import os,ctypes,uuid,time,threading,logging,json
from pathlib import Path
APP_ID='DrillingWorkbench.Desktop'
_branding_started=False

class GUID(ctypes.Structure):
 _fields_=[('data1',ctypes.c_uint32),('data2',ctypes.c_uint16),('data3',ctypes.c_uint16),('data4',ctypes.c_ubyte*8)]

def _guid(value):return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)

def _set_identity(store,root):
 from ctypes import wintypes as w
 class Key(ctypes.Structure):_fields_=[('fmtid',type(_guid('9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3'))),('pid',w.DWORD)]
 class Union(ctypes.Union):_fields_=[('text',w.LPWSTR),('padding',ctypes.c_byte*16)]
 class Value(ctypes.Structure):_anonymous_=('value',);_fields_=[('vt',w.WORD),('reserved1',w.WORD),('reserved2',w.WORD),('reserved3',w.WORD),('value',Union)]
 vtable=ctypes.cast(store,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
 setter=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.POINTER(Key),ctypes.POINTER(Value))(vtable[6]);commit=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p)(vtable[7])
 values={5:APP_ID,2:'"'+str(root/'鑽探工作台.exe')+'"',3:str(root/'鑽探工作台.exe')+',0',4:'@'+str(root/'鑽探工作台.exe')+',-101'}
 for pid,text in values.items():
  key=Key(_guid('9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3'),pid);buffer=ctypes.create_unicode_buffer(text);value=Value();value.vt=31;value.text=ctypes.cast(buffer,w.LPWSTR)
  result=setter(store,ctypes.byref(key),ctypes.byref(value))
  if result<0:raise OSError('Set taskbar property failed: '+hex(result&0xffffffff))
 result=commit(store)
 if result<0:raise OSError('Commit taskbar properties failed')

def _release(pointer):
 table=ctypes.cast(pointer,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
 ctypes.WINFUNCTYPE(ctypes.c_ulong,ctypes.c_void_p)(table[2])(pointer)

def stamp_shortcut(path,root):
 if os.name!='nt':return
 from ctypes import wintypes as w
 ole=ctypes.windll.ole32;ole.CoInitializeEx(None,2)
 persist=ctypes.c_void_p();store=ctypes.c_void_p()
 try:
  clsid=_guid('00021401-0000-0000-c000-000000000046');iid=_guid('0000010b-0000-0000-c000-000000000046')
  result=ole.CoCreateInstance(ctypes.byref(clsid),None,1,ctypes.byref(iid),ctypes.byref(persist))
  if result<0:raise OSError('Cannot open shortcut properties')
  table=ctypes.cast(persist,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
  load=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p,w.LPCWSTR,w.DWORD)(table[5]);save=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p,w.LPCWSTR,w.BOOL)(table[6])
  if load(persist,str(path),2)<0:raise OSError('Cannot load shortcut')
  query=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(table[0]);iid=_guid('886d8eeb-8cf2-4446-8d02-cdba1dbdcf99')
  if query(persist,ctypes.byref(iid),ctypes.byref(store))<0:raise OSError('Cannot access shortcut property store')
  _set_identity(store,root)
  if save(persist,str(path),True)<0:raise OSError('Cannot save shortcut properties')
 finally:
  if store:_release(store)
  if persist:_release(persist)
  ole.CoUninitialize()

def start_window_branding(root,browser):
 global _branding_started
 if os.name!='nt' or _branding_started:return
 _branding_started=True
 def worker():
  from ctypes import wintypes as w
  user=ctypes.windll.user32;kernel=ctypes.windll.kernel32;shell=ctypes.windll.shell32;ole=ctypes.windll.ole32;ole.CoInitializeEx(None,2)
  icon_path=str(root/'drilling-workbench-blue.ico')
  user.LoadImageW.argtypes=[w.HINSTANCE,w.LPCWSTR,w.UINT,ctypes.c_int,ctypes.c_int,w.UINT];user.LoadImageW.restype=w.HANDLE
  small=user.LoadImageW(None,icon_path,1,32,32,0x10);big=user.LoadImageW(None,icon_path,1,256,256,0x10)
  if not small or not big:logging.error('Cannot load supplied window icon');return
  enum_proc=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
  user.EnumWindows.argtypes=[enum_proc,w.LPARAM];user.IsWindowVisible.argtypes=[w.HWND];user.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
  user.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,ctypes.c_int];user.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,ctypes.c_int]
  kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
  kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)];kernel.CloseHandle.argtypes=[w.HANDLE]
  user.SendMessageTimeoutW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,ctypes.POINTER(ctypes.c_size_t)]
  user.SetClassLongPtrW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_ssize_t];user.SetClassLongPtrW.restype=ctypes.c_size_t
  shell.SHGetPropertyStoreForWindow.argtypes=[w.HWND,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)];shell.SHGetPropertyStoreForWindow.restype=ctypes.c_long
  expected=os.path.normcase(str(browser.resolve()));applied=set()
  @enum_proc
  def visit(hwnd,_):
   try:
    if not user.IsWindowVisible(hwnd):return True
    name=ctypes.create_unicode_buffer(256);user.GetClassNameW(hwnd,name,256)
    if not name.value.startswith('Chrome_WidgetWin_'):return True
    title=ctypes.create_unicode_buffer(1024);user.GetWindowTextW(hwnd,title,1024)
    if '鑽探工作台' not in title.value:return True
    pid=w.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid));handle=kernel.OpenProcess(0x1000,False,pid.value)
    if not handle:return True
    try:
     executable=ctypes.create_unicode_buffer(32768);size=w.DWORD(32768)
     if not kernel.QueryFullProcessImageNameW(handle,0,executable,ctypes.byref(size)) or os.path.normcase(executable.value)!=expected:return True
    finally:kernel.CloseHandle(handle)
    result=ctypes.c_size_t()
    for which,icon in [(0,small),(1,big)]:user.SendMessageTimeoutW(hwnd,0x80,which,int(icon),2,1000,ctypes.byref(result))
    user.SetClassLongPtrW(hwnd,-14,int(big));user.SetClassLongPtrW(hwnd,-34,int(small))
    if hwnd not in applied:
     store=ctypes.c_void_p();iid=_guid('886d8eeb-8cf2-4446-8d02-cdba1dbdcf99')
     if shell.SHGetPropertyStoreForWindow(hwnd,ctypes.byref(iid),ctypes.byref(store))>=0:
      try:_set_identity(store,root)
      finally:_release(store)
     applied.add(hwnd);logging.info('Applied workbench icon and taskbar identity to HWND %s',hwnd)
   except Exception:logging.exception('Window branding failed')
   return True
  try:
   # Repeat during startup because Chromium may set its own icon after page load.
   for _ in range(90):user.EnumWindows(visit,0);time.sleep(.5)
   while True:user.EnumWindows(visit,0);time.sleep(2)
  finally:ole.CoUninitialize()
 threading.Thread(target=worker,daemon=True).start()

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--shortcut',action='append',default=[]);args=parser.parse_args();root=Path(__file__).resolve().parent.parent
 failed=False
 for link in args.shortcut:
  try:stamp_shortcut(Path(link),root)
  except Exception:failed=True;logging.exception('Shortcut branding failed')
 raise SystemExit(1 if failed else 0)
