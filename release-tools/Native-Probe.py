import ctypes,json,sys,time,subprocess
from ctypes import wintypes as w
from pathlib import Path
root=Path(sys.argv[1]);action=sys.argv[2];u=ctypes.windll.user32;k=ctypes.windll.kernel32;s=ctypes.windll.shell32
u.FindWindowW.argtypes=[w.LPCWSTR,w.LPCWSTR];u.FindWindowW.restype=w.HWND
u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,ctypes.c_int];u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];u.SendMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];u.SendMessageW.restype=ctypes.c_ssize_t
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE;k.CloseHandle.argtypes=[w.HANDLE]
k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
callback=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM);windows=[]
@callback
def visit(hwnd,_):
 title=ctypes.create_unicode_buffer(1024);u.GetWindowTextW(hwnd,title,1024)
 if '鑽探工作台' not in title.value:return True
 pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid));process=k.OpenProcess(0x1000,False,pid.value)
 if process:
  try:
   name=ctypes.create_unicode_buffer(32768);length=w.DWORD(32768)
   if k.QueryFullProcessImageNameW(process,0,name,ctypes.byref(length)) and Path(name.value)==root/'browser/chrome.exe':windows.append(hwnd)
  finally:k.CloseHandle(process)
 return True
u.EnumWindows.argtypes=[callback,w.LPARAM];u.EnumWindows(visit,0)
tray=u.FindWindowW(None,'鑽探工作台背景服務')
if action=='close-windows':
 for hwnd in windows:u.PostMessageW(hwnd,0x10,0,0)
elif action=='double-click':
 assert tray,'Tray window absent';u.PostMessageW(tray,0x8001,0,0x203)
elif action=='menu-exit':
 assert tray,'Tray window absent';u.PostMessageW(tray,0x8001,0,0x205);time.sleep(1)
 # Invoke the actual native menu item through UI Automation; CI has no physical keyboard.
 command="""Add-Type -AssemblyName UIAutomationClient
 $name=[System.Windows.Automation.AutomationElement]::NameProperty
 $type=[System.Windows.Automation.AutomationElement]::ControlTypeProperty
 $c1=[System.Windows.Automation.PropertyCondition]::new($name,'結束程式')
 $c2=[System.Windows.Automation.PropertyCondition]::new($type,[System.Windows.Automation.ControlType]::MenuItem)
 $condition=[System.Windows.Automation.AndCondition]::new($c1,$c2)
 $element=[System.Windows.Automation.AutomationElement]::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Subtree,$condition)
 if(!$element){throw 'Native exit menu item unavailable'}
 try{$pattern=$element.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern);$pattern.Invoke()}
 catch{$pattern=$element.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern);$pattern.DoDefaultAction()}
 """
 import base64
 encoded=base64.b64encode(command.encode('utf-16-le')).decode('ascii')
 result=subprocess.run(['powershell.exe','-NoProfile','-EncodedCommand',encoded],capture_output=True,text=True,timeout=20)
 if result.returncode:raise RuntimeError('Native menu invocation failed: '+result.stderr)

info={'rootArgument':str(root),'resolvedRoot':str(root.resolve()),'dataFiles':[p.name for p in (root/'data').glob('*')],'instanceFile':(root/'data/desktop-instance.json').read_text(encoding='utf-8') if (root/'data/desktop-instance.json').exists() else None,'trayWindow':int(tray or 0),'browserWindows':len(windows),'windowIconHandles':[int(u.SendMessageW(h,0x7f,0,0)) for h in windows]}
if action=='info' and tray:
 class Identifier(ctypes.Structure):_fields_=[('size',w.DWORD),('hwnd',w.HWND),('id',w.UINT),('guid',ctypes.c_byte*16)]
 ident=Identifier();ident.size=ctypes.sizeof(ident);ident.hwnd=tray;ident.id=1;rect=w.RECT()
 s.Shell_NotifyIconGetRect.argtypes=[ctypes.POINTER(Identifier),ctypes.POINTER(w.RECT)];s.Shell_NotifyIconGetRect.restype=ctypes.c_long
 info['trayRectResult']=s.Shell_NotifyIconGetRect(ctypes.byref(ident),ctypes.byref(rect));info['trayRect']=[rect.left,rect.top,rect.right,rect.bottom]
print(json.dumps(info))
