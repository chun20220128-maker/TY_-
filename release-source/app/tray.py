"""Notification-area controls using only Windows APIs (no online dependencies)."""
import ctypes,os,threading,logging

def _windows(browser,action):
 if os.name!='nt' or not browser:return False
 from ctypes import wintypes as w
 u=ctypes.windll.user32;k=ctypes.windll.kernel32
 callback=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
 k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
 k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)];k.CloseHandle.argtypes=[w.HANDLE]
 u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,ctypes.c_int];u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
 u.ShowWindow.argtypes=[w.HWND,ctypes.c_int];u.SetForegroundWindow.argtypes=[w.HWND];u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
 found=[]
 @callback
 def visit(hwnd,_):
  title=ctypes.create_unicode_buffer(1024);u.GetWindowTextW(hwnd,title,1024)
  if '鑽探工作台' not in title.value:return True
  pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid));handle=k.OpenProcess(0x1000,False,pid.value)
  if not handle:return True
  try:
   name=ctypes.create_unicode_buffer(32768);size=w.DWORD(32768)
   if k.QueryFullProcessImageNameW(handle,0,name,ctypes.byref(size)) and os.path.normcase(name.value)==os.path.normcase(str(browser.resolve())):
    if action=='open':u.ShowWindow(hwnd,9);u.SetForegroundWindow(hwnd)
    else:u.PostMessageW(hwnd,0x10,0,0)
    found.append(hwnd)
  finally:k.CloseHandle(handle)
  return True
 u.EnumWindows.argtypes=[callback,w.LPARAM];u.EnumWindows(visit,0)
 return bool(found)

def focus_workbench(browser):return _windows(browser,'open')
def close_workbench(browser):return _windows(browser,'close')

class TrayIcon:
 def __init__(self,root,on_open,on_exit):self.root=root;self.on_open=on_open;self.on_exit=on_exit;self.hwnd=None;self.ready=threading.Event();self.error=None
 def start(self):
  if os.name!='nt':return
  self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()
  if not self.ready.wait(10):raise RuntimeError('無法建立工作台常駐圖示')
  if self.error:raise RuntimeError('無法建立工作台常駐圖示：'+str(self.error))
 def close(self):
  if self.hwnd:
   ctypes.windll.user32.PostMessageW(self.hwnd,0x10,0,0)
   self.thread.join(timeout=3)
 def _run(self):
  from ctypes import wintypes as w
  u=ctypes.windll.user32;k=ctypes.windll.kernel32;shell=ctypes.windll.shell32
  proc=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
  class WndClass(ctypes.Structure):
   _fields_=[('style',w.UINT),('proc',proc),('extra1',ctypes.c_int),('extra2',ctypes.c_int),('instance',w.HINSTANCE),('icon',w.HICON),('cursor',w.HANDLE),('background',w.HANDLE),('menu',w.LPCWSTR),('name',w.LPCWSTR)]
  class Notify(ctypes.Structure):
   _fields_=[('size',w.DWORD),('hwnd',w.HWND),('id',w.UINT),('flags',w.UINT),('callback',w.UINT),('icon',w.HICON),('tip',w.WCHAR*128),('state',w.DWORD),('mask',w.DWORD),('info',w.WCHAR*256),('version',w.UINT),('title',w.WCHAR*64),('infoflags',w.DWORD),('guid',ctypes.c_byte*16),('balloon',w.HICON)]
  u.RegisterWindowMessageW.argtypes=[w.LPCWSTR];u.RegisterWindowMessageW.restype=w.UINT
  u.RegisterClassW.argtypes=[ctypes.POINTER(WndClass)];u.RegisterClassW.restype=w.WORD
  u.GetMessageW.argtypes=[ctypes.POINTER(w.MSG),w.HWND,w.UINT,w.UINT];u.GetMessageW.restype=w.BOOL
  u.TranslateMessage.argtypes=[ctypes.POINTER(w.MSG)];u.DispatchMessageW.argtypes=[ctypes.POINTER(w.MSG)];u.DispatchMessageW.restype=ctypes.c_ssize_t
  u.GetCursorPos.argtypes=[ctypes.POINTER(w.POINT)]
  u.DefWindowProcW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];u.DefWindowProcW.restype=ctypes.c_ssize_t
  u.CreateWindowExW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.HWND,w.HMENU,w.HINSTANCE,ctypes.c_void_p];u.CreateWindowExW.restype=w.HWND
  k.GetModuleHandleW.argtypes=[w.LPCWSTR];k.GetModuleHandleW.restype=w.HINSTANCE
  u.LoadImageW.argtypes=[w.HINSTANCE,w.LPCWSTR,w.UINT,ctypes.c_int,ctypes.c_int,w.UINT];u.LoadImageW.restype=w.HANDLE
  u.CreatePopupMenu.restype=w.HMENU;u.AppendMenuW.argtypes=[w.HMENU,w.UINT,ctypes.c_size_t,w.LPCWSTR]
  u.TrackPopupMenu.argtypes=[w.HMENU,w.UINT,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.HWND,ctypes.c_void_p];u.TrackPopupMenu.restype=w.UINT
  u.DestroyMenu.argtypes=[w.HMENU];u.DestroyWindow.argtypes=[w.HWND];u.SetForegroundWindow.argtypes=[w.HWND]
  u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];u.DestroyIcon.argtypes=[w.HICON]
  shell.Shell_NotifyIconW.argtypes=[w.DWORD,ctypes.POINTER(Notify)];shell.Shell_NotifyIconW.restype=w.BOOL
  icon=None;registered=False;data=None
  try:
   taskbar_created=u.RegisterWindowMessageW('TaskbarCreated')
   def add_icon():
    if not shell.Shell_NotifyIconW(0,ctypes.byref(data)):raise OSError('Shell_NotifyIconW failed')
   @proc
   def callback(hwnd,msg,wp,lp):
    try:
     if msg==taskbar_created:add_icon();return 0
     if msg==0x8001:
      if lp==0x203:threading.Thread(target=self.on_open,daemon=True).start()
      elif lp in (0x205,0x7b):
       menu=u.CreatePopupMenu();u.AppendMenuW(menu,0,1,'開啟鑽探工作台');u.AppendMenuW(menu,0x800,0,None);u.AppendMenuW(menu,0,2,'結束程式')
       point=w.POINT();u.GetCursorPos(ctypes.byref(point));u.SetForegroundWindow(hwnd)
       selection=u.TrackPopupMenu(menu,0x100|0x2,point.x,point.y,0,hwnd,None);u.DestroyMenu(menu);u.PostMessageW(hwnd,0,0,0)
       if selection:threading.Thread(target=self.on_open if selection==1 else self.on_exit,daemon=True).start()
      return 0
     if msg==0x10:u.DestroyWindow(hwnd);return 0
     if msg==2:u.PostQuitMessage(0);return 0
    except Exception:logging.exception('Tray operation failed')
    return u.DefWindowProcW(hwnd,msg,wp,lp)
   instance=k.GetModuleHandleW(None);name='DrillingWorkbenchTray-'+str(os.getpid());wc=WndClass();wc.proc=callback;wc.instance=instance;wc.name=name
   if not u.RegisterClassW(ctypes.byref(wc)):raise OSError('RegisterClassW failed')
   registered=True
   self.hwnd=u.CreateWindowExW(0,name,'鑽探工作台背景服務',0,0,0,0,0,None,None,instance,None)
   if not self.hwnd:raise OSError('CreateWindowExW failed')
   icon=u.LoadImageW(None,str(self.root/'drilling-workbench-blue.ico'),1,32,32,0x10)
   if not icon:raise OSError('Cannot load tray icon')
   data=Notify();data.size=ctypes.sizeof(data);data.hwnd=self.hwnd;data.id=1;data.flags=1|2|4;data.callback=0x8001;data.icon=icon;data.tip='鑽探工作台正在執行｜雙擊開啟・右鍵結束程式'
   add_icon();self.ready.set();message=w.MSG()
   while u.GetMessageW(ctypes.byref(message),None,0,0)>0:u.TranslateMessage(ctypes.byref(message));u.DispatchMessageW(ctypes.byref(message))
  except Exception as error:self.error=error;logging.exception('Tray initialization failed');self.ready.set()
  finally:
   if data:shell.Shell_NotifyIconW(2,ctypes.byref(data))
   if icon:u.DestroyIcon(icon)
   if registered:
    u.UnregisterClassW.argtypes=[w.LPCWSTR,w.HINSTANCE];u.UnregisterClassW(name,instance)
   self.hwnd=None
