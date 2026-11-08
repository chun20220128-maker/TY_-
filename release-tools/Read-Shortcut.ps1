Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
[ComImport, Guid("00021401-0000-0000-C000-000000000046")]
class NativeShellLink {}
[ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface NativeIShellLinkW {
 void GetPath([Out,MarshalAs(UnmanagedType.LPWStr)] StringBuilder path,int max,IntPtr data,uint flags);
 void GetIDList(out IntPtr id);
 void SetIDList(IntPtr id);
 void GetDescription([Out,MarshalAs(UnmanagedType.LPWStr)] StringBuilder text,int max);
 void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string text);
 void GetWorkingDirectory([Out,MarshalAs(UnmanagedType.LPWStr)] StringBuilder text,int max);
 void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string text);
 void GetArguments([Out,MarshalAs(UnmanagedType.LPWStr)] StringBuilder text,int max);
 void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string text);
 void GetHotkey(out short key);
 void SetHotkey(short key);
 void GetShowCmd(out int cmd);
 void SetShowCmd(int cmd);
 void GetIconLocation([Out,MarshalAs(UnmanagedType.LPWStr)] StringBuilder path,int max,out int index);
 void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path,int index);
 void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path,uint reserved);
 void Resolve(IntPtr window,uint flags);
 void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
}
public class NativeShortcutInfo {public string Target;public string Icon;public int IconIndex;}
public static class NativeShortcutReader {
 public static NativeShortcutInfo Read(string path){
  object obj=new NativeShellLink();
  try {
   ((IPersistFile)obj).Load(path,0);
   var link=(NativeIShellLinkW)obj;
   var target=new StringBuilder(32768);var icon=new StringBuilder(32768);int index;
   link.GetPath(target,target.Capacity,IntPtr.Zero,0);
   link.GetIconLocation(icon,icon.Capacity,out index);
   return new NativeShortcutInfo{Target=target.ToString(),Icon=icon.ToString(),IconIndex=index};
  } finally {Marshal.FinalReleaseComObject(obj);}
 }
}
'@
