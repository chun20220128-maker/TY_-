"""Real Win32 tray registration/removal and deterministic menu-event selection.
No physical mouse or keyboard action is claimed by this test.
"""
import sys,ctypes,threading,json,time
from pathlib import Path
from ctypes import wintypes as w
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'app'));from tray import TrayIcon
u=ctypes.windll.user32;s=ctypes.windll.shell32;opened=threading.Event();exited=threading.Event();menus=[]
u.GetMenuStringW.argtypes=[w.HMENU,w.UINT,w.LPWSTR,ctypes.c_int,w.UINT]
original=u.TrackPopupMenu
def select_exit(menu,*args):
 labels=[]
 for index in (0,2):
  text=ctypes.create_unicode_buffer(100);u.GetMenuStringW(menu,index,text,100,0x400);labels.append(text.value)
 menus.append(labels);return 2
u.TrackPopupMenu=select_exit
tray=TrayIcon(root,opened.set,exited.set)
class Identifier(ctypes.Structure):_fields_=[('size',w.DWORD),('hwnd',w.HWND),('id',w.UINT),('guid',ctypes.c_byte*16)]
s.Shell_NotifyIconGetRect.argtypes=[ctypes.POINTER(Identifier),ctypes.POINTER(w.RECT)];s.Shell_NotifyIconGetRect.restype=ctypes.c_long
try:
 tray.start();handle=tray.hwnd;ident=Identifier();ident.size=ctypes.sizeof(ident);ident.hwnd=handle;ident.id=1;rect=w.RECT()
 assert s.Shell_NotifyIconGetRect(ctypes.byref(ident),ctypes.byref(rect))==0
 u.PostMessageW(handle,0x8001,0,0x203);assert opened.wait(5),'Double-click handler did not run'
 u.PostMessageW(handle,0x8001,0,0x205);assert exited.wait(5),'Menu exit handler did not run'
 assert menus==[['開啟鑽探工作台','結束程式']],menus
 tray.close();assert not tray.hwnd
 assert s.Shell_NotifyIconGetRect(ctypes.byref(ident),ctypes.byref(rect))!=0,'Stopped tray icon still registered'
 print(json.dumps({'nativeNotificationIconRegistered':True,'nativeIconRemovedAfterStop':True,'doubleClickEvent':True,'nativeMenuLabels':menus[0],'menuSelectionHandler':True,'physicalMouseInteractionTested':False}))
finally:tray.close();u.TrackPopupMenu=original
