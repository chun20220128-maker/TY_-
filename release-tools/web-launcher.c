#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR command,int show){
 wchar_t root[32768],python[32768],params[32768],app[32768];DWORD size=sizeof(root);
 if(RegGetValueW(HKEY_CURRENT_USER,L"Software\\DrillingWorkbench",L"InstallDir",RRF_RT_REG_SZ,NULL,root,&size)!=ERROR_SUCCESS){MessageBoxW(NULL,L"請先安裝鑽探工作台完整離線版，再使用本機網頁入口。",L"鑽探工作台",MB_ICONINFORMATION);return 1;}
 if(swprintf(python,32768,L"%ls\\runtime\\pythonw.exe",root)<0||swprintf(app,32768,L"%ls\\app",root)<0)return 1;
 /* This shim also works with installed 1.0.4, without changing any user files. */
 const wchar_t *code=L"import sys,os;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import windows_app as a;c=[Path(b)/p for b in [os.environ.get('PROGRAMFILES',''),os.environ.get('PROGRAMFILES(X86)',''),os.environ.get('LOCALAPPDATA','')] if b for p in ['Microsoft/Edge/Application/msedge.exe','Google/Chrome/Application/chrome.exe']];browser=next((p for p in c if p.is_file()),None);a.find_browser=lambda:browser;a.main()";
 if(swprintf(params,32768,L"-I -X utf8 -c \"%ls\" \"%ls\"",code,app)<0)return 1;
 SHELLEXECUTEINFOW launch={0};launch.cbSize=sizeof(launch);launch.fMask=SEE_MASK_NOCLOSEPROCESS;launch.lpFile=python;launch.lpParameters=params;launch.lpDirectory=root;launch.nShow=SW_HIDE;
 if(!ShellExecuteExW(&launch)){MessageBoxW(NULL,L"無法開啟本機網頁入口。請重新執行完整安裝檔修復，並確認電腦已有 Microsoft Edge 或 Google Chrome。",L"鑽探工作台",MB_ICONERROR);return 1;}
 if(launch.hProcess)CloseHandle(launch.hProcess);return 0;
}
