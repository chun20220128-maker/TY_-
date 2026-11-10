"""Verify Win32 activation contexts and reproduce missing-private-assembly 14001."""
import ctypes,sys,json,subprocess
from ctypes import wintypes as w
from pathlib import Path
folder=Path(sys.argv[1]).resolve();version='157.0.8103.39';kernel=ctypes.WinDLL('kernel32',use_last_error=True)
class Context(ctypes.Structure):
 _fields_=[('size',w.ULONG),('flags',w.DWORD),('source',w.LPCWSTR),('architecture',w.USHORT),('language',w.LANGID),('directory',w.LPCWSTR),('resource',ctypes.c_void_p),('application',w.LPCWSTR),('module',w.HMODULE)]
kernel.CreateActCtxW.argtypes=[ctypes.POINTER(Context)];kernel.CreateActCtxW.restype=w.HANDLE;kernel.ReleaseActCtx.argtypes=[w.HANDLE]
def activation():
 context=Context();context.size=ctypes.sizeof(context);context.flags=8;context.source=str(folder/'chrome.exe');context.resource=1
 handle=kernel.CreateActCtxW(ctypes.byref(context))
 if handle==ctypes.c_void_p(-1).value:return ctypes.get_last_error()
 kernel.ReleaseActCtx(handle);return 0
if '--probe' in sys.argv:
 print(activation());raise SystemExit(0)
assert activation()==0,'Intact browser activation context failed'
if '--reproduce-missing' in sys.argv:
 manifest=folder/version/(version+'.manifest');backup=manifest.with_suffix('.manifest.test-backup');manifest.rename(backup)
 try:
  error=int(subprocess.check_output([sys.executable,str(Path(__file__).resolve()),str(folder),'--probe'],text=True).strip())
  process_error=None
  try:
   process=subprocess.Popen([str(folder/'chrome.exe'),'--version'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  except OSError as exc:process_error=exc.winerror
  else:process.terminate();process.wait(timeout=10);process_error=0

 finally:backup.rename(manifest)
 print(json.dumps({'oldMissingManifestActivation':error,'oldMissingManifestProcessError':process_error,'userMachineFailureNotAssumedReproduced':True,'restoredAfterTest':activation()==0}))
else:
 assert not (folder/version).exists(),'Version-dependent subfolder still required'
 for name in ['chrome.dll','chrome_elf.dll',version+'.manifest','icudtl.dat','v8_context_snapshot.bin']:assert (folder/name).is_file(),name
 setlang=kernel.SetThreadPreferredUILanguages;setlang.argtypes=[w.DWORD,w.LPCWSTR,ctypes.POINTER(w.ULONG)]
 results={}
 for language in ['en-US','zh-TW','zh-CN']:
  count=w.ULONG();assert setlang(8,language+'\0\0',ctypes.byref(count));results[language]=activation();assert results[language]==0,(language,results[language])
 print(json.dumps({'flatActivationContext':results,'externalVCAssemblyRequired':False}))
