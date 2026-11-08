#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR command,int show){
 wchar_t root[32768],python[32768],params[32768];DWORD n=GetModuleFileNameW(NULL,root,32768);if(!n||n>=32768)return 1;wchar_t *slash=wcsrchr(root,L'\\');if(!slash)return 1;*slash=0;
 if(swprintf(python,32768,L"%ls\\runtime\\pythonw.exe",root)<0||swprintf(params,32768,L"-I -X utf8 \"%ls\\app\\windows_app.py\"",root)<0)return 1;
 SHELLEXECUTEINFOW launch={0};launch.cbSize=sizeof(launch);launch.fMask=SEE_MASK_NOCLOSEPROCESS;launch.lpFile=python;launch.lpParameters=params;launch.lpDirectory=root;launch.nShow=SW_HIDE;
 if(!ShellExecuteExW(&launch)){MessageBoxW(NULL,L"無法啟動。請先將整份 ZIP 解壓縮，再開啟鑽探工作台.exe；請保留 runtime、app、data 資料夾。",L"鑽探工作台",MB_ICONERROR);return 1;}if(launch.hProcess)CloseHandle(launch.hProcess);return 0;
}
