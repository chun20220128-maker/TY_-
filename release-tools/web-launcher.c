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
 const wchar_t *code=L"import sys,os;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import windows_app as a;c=[Path(b)/p for b in [os.environ.get('PROGRAMFILES',''),os.environ.get('PROGRAMFILES(X86)',''),os.environ.get('LOCALAPPDATA','')] if b for p in ['Microsoft/Edge/Application/msedge.exe','Google/Chrome/Application/chrome.exe']];browser=next((p for p in c if p.is_file()),None);a.find_browser=lambda:browser;original=a.open_browser;exec(bytes.fromhex('69662062726f77736572206973204e6f6e653a0a20612e616c6572742827e69cace6a99fe7b6b2e9a081e585a5e58fa3e99c80e8a681e99bbbe885a6e58e9fe69c89e79a84204d6963726f736f6674204564676520e6889620476f6f676c65204368726f6d65e3808227293b72616973652053797374656d457869742831290a646566206f70656e5f7765622875726c2c7072656665725f6578697374696e673d54727565293a0a206f6c643d612e444154410a207472793a0a2020612e444154413d6f6c642f277765622d766965772d64617461273b612e444154412e6d6b6469722865786973745f6f6b3d54727565290a202072657475726e206f726967696e616c2875726c2c7072656665725f6578697374696e67290a2066696e616c6c793a20612e444154413d6f6c640a').decode());a.open_browser=open_web;a.main()";
 if(swprintf(params,32768,L"-I -X utf8 -c \"%ls\" \"%ls\"",code,app)<0)return 1;
 SHELLEXECUTEINFOW launch={0};launch.cbSize=sizeof(launch);launch.fMask=SEE_MASK_NOCLOSEPROCESS;launch.lpFile=python;launch.lpParameters=params;launch.lpDirectory=root;launch.nShow=SW_HIDE;
 if(!ShellExecuteExW(&launch)){MessageBoxW(NULL,L"無法開啟本機網頁入口。請重新執行完整安裝檔修復，並確認電腦已有 Microsoft Edge 或 Google Chrome。",L"鑽探工作台",MB_ICONERROR);return 1;}
 if(launch.hProcess)CloseHandle(launch.hProcess);return 0;
}
