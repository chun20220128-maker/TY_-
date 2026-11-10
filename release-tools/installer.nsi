Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!ifndef STAGE
 !error "Define STAGE (offline payload directory)"
!endif
!ifndef OUTPUT
 !error "Define OUTPUT (Setup.exe)"
!endif
!define MUI_ICON "${STAGE}\drilling-workbench-blue.ico"
!define MUI_UNICON "${STAGE}\drilling-workbench-blue.ico"
Name "鑽探工作台"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\DrillingWorkbench"
InstallDirRegKey HKCU "Software\DrillingWorkbench" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
CRCCheck force
ShowInstDetails show
ShowUninstDetails show
VIProductVersion "1.0.5.0"
VIAddVersionKey /LANG=1028 "ProductName" "鑽探工作台 Windows 單機版"
VIAddVersionKey /LANG=1028 "FileDescription" "鑽探工作台完整離線安裝程式"
VIAddVersionKey /LANG=1028 "FileVersion" "1.0.5.0"
VIAddVersionKey /LANG=1028 "ProductVersion" "1.0.5"
VIAddVersionKey /LANG=1028 "LegalCopyright" "鑽探工作台"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "鑽探工作台 Windows 單機版"
!define MUI_WELCOMEPAGE_TEXT "本程式包含規劃、估價、契約、請款及歷史契約單價。$\r$\n$\r$\n安裝程式已內含必要的執行與視窗元件，安裝及使用都不需要網路，不需要另外安裝 Python 或瀏覽器。$\r$\n$\r$\n資料儲存在安裝資料夾的 data 目錄中。升級及解除安裝都會保留此目錄。$\r$\n$\r$\n若工作台已開啟，請先按左側「結束程式」並關閉工作台視窗。"
!insertmacro MUI_PAGE_WELCOME
!define MUI_DIRECTORYPAGE_TEXT_TOP "請選擇您可以寫入的資料夾。建議保留預設位置，勿選擇需要系統管理員權限的 Program Files。歷史單價保存在安裝位置的 data 資料夾；專案作業請自行匯出備份。"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\鑽探工作台.exe"
!define MUI_FINISHPAGE_RUN_TEXT "啟動鑽探工作台"
!define MUI_FINISHPAGE_TEXT "鑽探工作台已安裝完成。$\r$\n$\r$\n可從桌面或開始功能表啟動，不需要網路。歷史契約單價自動保存在本機。專案作業須自行匯出備份，結束後不保留。$\r$\n$\r$\n日後請定期將整個 data 資料夾備份到其他磁碟。"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH
!insertmacro MUI_LANGUAGE "TradChinese"

Function .onInit
 ${IfNot} ${RunningX64}
  MessageBox MB_ICONSTOP "此安裝程式適用 Windows 10／11 的 64 位元（x64）電腦。"
  Abort
 ${EndIf}
 ${IfNot} ${AtLeastWin10}
  MessageBox MB_ICONSTOP "鑽探工作台需要 Windows 10 或 Windows 11。"
  Abort
 ${EndIf}
 SetRegView 64
 SetShellVarContext current
FunctionEnd

; A loaded Python DLL or Chromium EXE is write-protected by Windows.
; Only test existing files; opening in append mode without writing preserves bytes.
!macro CheckClosed PREFIX
Function ${PREFIX}CheckClosed
 retry_check:
 IfFileExists "$INSTDIR\runtime\python312.dll" 0 check_browser
 ClearErrors
 FileOpen $0 "$INSTDIR\runtime\python312.dll" a
 IfErrors running
 FileClose $0
 check_browser:
 IfFileExists "$INSTDIR\browser\chrome.exe" 0 check_done
 ClearErrors
 FileOpen $0 "$INSTDIR\browser\chrome.exe" a
 IfErrors running
 FileClose $0
 Goto check_done
 running:
 MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "工作台仍在執行，或資料夾無寫入權限。請先按工作台左側「結束程式」、關閉工作台視窗，再按「重試」。" IDRETRY retry_check
 Abort
 check_done:
FunctionEnd
!macroend
!insertmacro CheckClosed ""
!insertmacro CheckClosed "un."

Section "鑽探工作台（完整離線版）"
 Call CheckClosed
 SetShellVarContext current
 SetRegView 64
 SetOverwrite on
 SetOutPath "$INSTDIR"
 File /oname=鑽探工作台.exe "${STAGE}\DrillingWorkbench.exe"
 File /oname=鑽探工作台-網頁入口.exe "${STAGE}\DrillingWorkbench_Web_Start.exe"
 File "${STAGE}\drilling-workbench-blue.ico"
 File /oname=使用說明.txt "${STAGE}\README.zh-TW.txt"
 File "${STAGE}\THIRD-PARTY-NOTICES.txt"
 File "${STAGE}\MINGW-LICENSE.txt"
 File "${STAGE}\CHROMIUM-LICENSE.txt"
 File "${STAGE}\release-manifest.json"
 SetOutPath "$INSTDIR\app"
 File /r /x "__pycache__" "${STAGE}\app\*"
 SetOutPath "$INSTDIR\runtime"
 File /r /x "__pycache__" "${STAGE}\runtime\*"
 SetOutPath "$INSTDIR\browser"
 File /r "${STAGE}\browser\*"
 CreateDirectory "$INSTDIR\exports"
 CreateDirectory "$INSTDIR\data"
 ; Seed only a new database. Existing libraries, projects and backups are untouched.
 IfFileExists "$INSTDIR\data\history.sqlite3" keep_history
 SetOutPath "$INSTDIR\data"
 SetOverwrite off
 File "${STAGE}\data\history.sqlite3"
 File "${STAGE}\data\history-backup.sqlite3"
 SetOverwrite on
 keep_history:
 SetOutPath "$INSTDIR"
 WriteUninstaller "$INSTDIR\解除安裝.exe"
 CreateDirectory "$SMPROGRAMS\鑽探工作台"
 CreateShortcut "$SMPROGRAMS\鑽探工作台\鑽探工作台.lnk" "$INSTDIR\鑽探工作台.exe" "" "$INSTDIR\鑽探工作台.exe" 0 SW_SHOWNORMAL "" "鑽探工作台（離線單機版）"
 CreateShortcut "$SMPROGRAMS\鑽探工作台\使用說明.lnk" "$INSTDIR\使用說明.txt"
 CreateShortcut "$SMPROGRAMS\鑽探工作台\資料資料夾.lnk" "$INSTDIR\data"
 CreateShortcut "$SMPROGRAMS\鑽探工作台\解除安裝.lnk" "$INSTDIR\解除安裝.exe"
 CreateShortcut "$DESKTOP\鑽探工作台.lnk" "$INSTDIR\鑽探工作台.exe" "" "$INSTDIR\鑽探工作台.exe" 0 SW_SHOWNORMAL "" "鑽探工作台（離線單機版）"
 CreateShortcut "$SMPROGRAMS\鑽探工作台\鑽探工作台（本機網頁入口）.lnk" "$INSTDIR\鑽探工作台-網頁入口.exe" "" "$INSTDIR\鑽探工作台-網頁入口.exe" 0
 WriteRegStr HKCU "Software\DrillingWorkbench" "InstallDir" "$INSTDIR"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DrillingWorkbench" "DisplayName" "鑽探工作台 Windows 單機版"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DrillingWorkbench" "DisplayVersion" "1.0.5"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DrillingWorkbench" "InstallLocation" "$INSTDIR"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DrillingWorkbench" "DisplayIcon" '"$INSTDIR\鑽探工作台.exe",0' 
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DrillingWorkbench" "UninstallString" '"$INSTDIR\解除安裝.exe"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DrillingWorkbench" "QuietUninstallString" '"$INSTDIR\解除安裝.exe" /S'
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DrillingWorkbench" "NoModify" 1
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DrillingWorkbench" "NoRepair" 1
SectionEnd

Function un.onInit
 SetShellVarContext current
 SetRegView 64
FunctionEnd

Section "Uninstall"
 Call un.CheckClosed
 SetShellVarContext current
 SetRegView 64
 Delete "$DESKTOP\鑽探工作台.lnk"
 RMDir /r "$SMPROGRAMS\鑽探工作台"
 RMDir /r "$INSTDIR\app"
 RMDir /r "$INSTDIR\runtime"
 RMDir /r "$INSTDIR\browser"
 Delete "$INSTDIR\鑽探工作台.exe"
 Delete "$INSTDIR\鑽探工作台-網頁入口.exe"
 Delete "$INSTDIR\drilling-workbench-blue.ico"
 Delete "$INSTDIR\使用說明.txt"
 Delete "$INSTDIR\THIRD-PARTY-NOTICES.txt"
 Delete "$INSTDIR\MINGW-LICENSE.txt"
 Delete "$INSTDIR\CHROMIUM-LICENSE.txt"
 Delete "$INSTDIR\release-manifest.json"
 Delete "$INSTDIR\解除安裝.exe"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DrillingWorkbench"
 DeleteRegKey HKCU "Software\DrillingWorkbench"
 ; Intentionally never remove $INSTDIR, data or exports.
 IfSilent uninstall_done
 MessageBox MB_OK "程式已解除安裝。$\r$\n歷史單價、專案資料及匯出檔案仍保留於：$\r$\n$INSTDIR\data$\r$\n$INSTDIR\exports"
 uninstall_done:
SectionEnd
