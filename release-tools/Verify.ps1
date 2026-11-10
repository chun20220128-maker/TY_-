$ErrorActionPreference='Stop'
$repo=$env:GITHUB_WORKSPACE;$source=Join-Path $repo 'release-tools';$report=Join-Path $repo 'verification';New-Item $report -ItemType Directory -Force|Out-Null
$setup=Join-Path $repo 'candidate/DrillingWorkbench_Setup_1.0.5_x64.exe';$meta=Get-Content 'candidate/Build_Report.json' -Raw -Encoding utf8|ConvertFrom-Json
if((Get-FileHash $setup -Algorithm SHA256).Hash.ToLower() -ne $meta.sha256){throw 'Installer checksum mismatch'}
$root=Join-Path $env:RUNNER_TEMP '鑽探工作台 離線測試'
# The installer, Python hosts and bundled browser have outbound Internet blocked throughout install/use tests.
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True
if(@(Get-NetFirewallProfile|Where-Object {!$_.Enabled}).Count){throw 'Firewall not enabled'}
$paths=@($setup,"$root\runtime\python.exe","$root\runtime\pythonw.exe","$root\browser\chrome.exe")
foreach($program in $paths){New-NetFirewallRule -DisplayName ('Workbench offline '+[guid]::NewGuid()) -Direction Outbound -Action Block -RemoteAddress @("1.0.0.0-126.255.255.255","128.0.0.0-223.255.255.255","2000::/3","fc00::/7","fe80::/10") -Program $program -Profile Any|Out-Null}
$process=Start-Process -FilePath $setup -ArgumentList "/S /D=$root" -Wait -PassThru
if($process.ExitCode -ne 0){throw 'Offline installation failed'}
$networkProbe="import socket;blocked=False
try: socket.create_connection(('1.1.1.1',443),timeout=3).close()
except OSError: blocked=True
assert blocked,'Product runtime still has Internet access'
print('PASS product runtime Internet blocked')"
& "$root\runtime\python.exe" -X utf8 -c $networkProbe
if($LASTEXITCODE -ne 0){throw 'Offline firewall verification failed'}
$manifest=Get-Content "$root\release-manifest.json" -Raw -Encoding utf8|ConvertFrom-Json -AsHashtable
foreach($name in $manifest.files.Keys){if((Get-FileHash (Join-Path $root $name) -Algorithm SHA256).Hash.ToLower() -ne $manifest.files[$name]){throw "Installed payload mismatch: $name"}}
. "$source\Read-Shortcut.ps1"
$desktop=[Environment]::GetFolderPath('Desktop');$menu=Join-Path ([Environment]::GetFolderPath('Programs')) '鑽探工作台'
foreach($path in @("$desktop\鑽探工作台.lnk","$menu\鑽探工作台.lnk")){
 $link=[NativeShortcutReader]::Read($path)
 if($link.Target -ne "$root\鑽探工作台.exe" -or $link.Icon -ne "$root\鑽探工作台.exe" -or $link.IconIndex -ne 0){throw 'Shortcut target or icon mismatch'}
}
if(!(Get-Process explorer -ErrorAction SilentlyContinue)){Start-Process explorer.exe;Start-Sleep 5}
function Probe($action){$raw=& "$root\runtime\python.exe" "$source\Native-Probe.py" $root $action;if($LASTEXITCODE -ne 0){throw 'Native probe failed'};return ($raw|ConvertFrom-Json)}
function Open-Workbench {
 Remove-Item "$root\data\desktop-instance.json" -Force -ErrorAction SilentlyContinue
 Start-Process "$root\鑽探工作台.exe"
 for($i=0;$i -lt 60;$i++){
  Start-Sleep 1
  if(Test-Path "$root\data\desktop-instance.json"){
   $instance=Get-Content "$root\data\desktop-instance.json" -Raw -Encoding utf8|ConvertFrom-Json;$url="http://127.0.0.1:$($instance.port)"
   try{if((Invoke-RestMethod "$url/api/desktop-info").app -eq 'drilling-workbench-windows-v1' -and (Probe 'info').trayWindow -and (Probe 'info').trayRectResult -ge 0){return $url}}catch{}
  }
 }
 if(Test-Path "$root\data\desktop.log"){Get-Content "$root\data\desktop.log" -Tail 80 -Encoding utf8}
 if(Test-Path "$root\data\desktop-instance.json"){Get-Content "$root\data\desktop-instance.json" -Raw -Encoding utf8}
 Write-Host "Expected root: $root"
 Probe 'info'|ConvertTo-Json -Depth 10|Write-Host
 Get-ChildItem "$root\data" -Force|Select-Object Name,Length|Format-Table
 Get-CimInstance Win32_Process|Where-Object {$_.Name -in @('pythonw.exe','chrome.exe')}|Select-Object Name,ProcessId,ExecutablePath,CommandLine|Format-List
 Get-CimInstance Win32_Process|Where-Object {$_.ExecutablePath -and $_.ExecutablePath.StartsWith($root)}|Select-Object Name,ProcessId,CommandLine|Format-Table
 throw 'Native startup or notification icon failed' 
}
function Wait-Closed {
 for($i=0;$i -lt 30;$i++){
  $remaining=@(Get-CimInstance Win32_Process|Where-Object {$_.ExecutablePath -and $_.ExecutablePath.StartsWith($root) -and $_.Name -ne 'python.exe'})
  if($remaining.Count -eq 0){break};Start-Sleep 1
 }
 if($remaining.Count){$remaining|Format-Table Name,ProcessId,ExecutablePath;throw 'Workbench processes did not fully stop'}
 if((Probe 'info').trayWindow){throw 'Tray icon owner still running after exit'}
}
& "$root\runtime\python.exe" -X utf8 "$source\Test-Tray-Events.py" $root | Out-File "$report\Native_Tray_Events.json" -Encoding utf8
if($LASTEXITCODE -ne 0){throw 'Native tray registration or event test failed'}
$url=Open-Workbench
$history=Invoke-RestMethod "$url/api/history";if($history.records.Count -ne 322 -or $history.projectCount -ne 14){throw 'Bundled 14/322 history missing'}
$native=Probe 'info';$native|ConvertTo-Json -Depth 10|Out-File "$report\Native_Icon_Verification.json" -Encoding utf8
if($native.trayRectResult -lt 0){throw 'Windows cannot locate the running notification icon'}
Probe 'close-windows'|Out-Null;Start-Sleep 2
if(!(Probe 'info').trayWindow){throw 'X removed background icon'}
node "$source\Test-UI.cjs" $root $url 'full' $report
if($LASTEXITCODE -ne 0){if(Test-Path "$root\data\desktop.log"){Get-Content "$root\data\desktop.log" -Tail 60 -Encoding utf8};throw 'Offline native UI test failed'}
Wait-Closed
$url=Open-Workbench
node "$source\Test-UI.cjs" $root $url 'restart' $report
if($LASTEXITCODE -ne 0){throw 'Cold restart or backup restore test failed'}
Wait-Closed
# Launch the tiny web entry against the original 1.0.4 host, using the installed Edge/Chrome.
$hostSource=Get-Content "$root\app\windows_app.py" -Raw -Encoding utf8
Copy-Item "$source\Legacy-Host-1.0.4.py" "$root\app\windows_app.py" -Force
try{
 Start-Process (Join-Path $repo 'candidate/DrillingWorkbench_Web_Start.exe')
 $webReady=$false
 for($i=0;$i -lt 60;$i++){
  Start-Sleep 1
  if(Test-Path "$root\data\desktop-instance.json"){
   $instance=Get-Content "$root\data\desktop-instance.json" -Raw -Encoding utf8|ConvertFrom-Json;$url="http://127.0.0.1:$($instance.port)"
   try{$project=(Invoke-RestMethod "$url/api/project").project;if($project -and $project.project.name -eq ''){$webReady=$true;break}}catch{}
  }
 }
 if(!$webReady){throw 'Local web entry could not render legacy 1.0.4 through system browser'}
 if((Invoke-RestMethod "$url/api/history").records.Count -ne 323){throw 'Web entry did not retain the existing history database'}
 Invoke-RestMethod "$url/api/desktop-stop" -Method Post|Out-Null
 Start-Sleep 3
 # The system browser has its own executable outside the installation root.
 for($i=0;$i -lt 20 -and (Probe 'info').trayWindow;$i++){Start-Sleep 1}
 if((Probe 'info').trayWindow){throw 'Legacy web entry did not fully stop'}
 @{legacyHost='1.0.4';systemBrowserRendered=$true;historyRetained=323;noReinstallRequired=$true}|ConvertTo-Json|Out-File "$report\Web_Entry_Verification.json" -Encoding utf8
}finally{[IO.File]::WriteAllText("$root\app\windows_app.py",$hostSource,[Text.UTF8Encoding]::new($false))}
$historyBefore=(Get-FileHash "$root\data\history.sqlite3" -Algorithm SHA256).Hash
$backupBefore=(Get-FileHash "$root\exports\native-project-backup.json" -Algorithm SHA256).Hash
# Preserve a user-owned legacy project file without loading it or altering it.
[IO.File]::WriteAllText("$root\data\current-project.json",'{"legacy":"user-owned-old-save"}',[Text.UTF8Encoding]::new($false));$legacyBefore=(Get-FileHash "$root\data\current-project.json" -Algorithm SHA256).Hash
$process=Start-Process -FilePath $setup -ArgumentList "/S /D=$root" -Wait -PassThru
if($process.ExitCode -ne 0){throw 'Upgrade failed'}
foreach($check in @(@("$root\data\history.sqlite3",$historyBefore),@("$root\exports\native-project-backup.json",$backupBefore),@("$root\data\current-project.json",$legacyBefore))){if((Get-FileHash $check[0] -Algorithm SHA256).Hash -ne $check[1]){throw 'Upgrade changed user data'}}
$process=Start-Process -FilePath "$root\解除安裝.exe" -ArgumentList '/S' -Wait -PassThru
if($process.ExitCode -ne 0){throw 'Uninstall failed'};Start-Sleep 3
foreach($check in @(@("$root\data\history.sqlite3",$historyBefore),@("$root\exports\native-project-backup.json",$backupBefore),@("$root\data\current-project.json",$legacyBefore))){if((Get-FileHash $check[0] -Algorithm SHA256).Hash -ne $check[1]){throw 'Uninstall removed user data'}}
if(Test-Path "$root\鑽探工作台.exe"){throw 'Uninstall left launcher installed'}
@{runner=$env:RUNNER_OS;os=[Environment]::OSVersion.VersionString;offlineFirewallRules=$true;nativeInstall=$true;nativeLauncher=$true;nativeShortcuts=$true;trayPresentWhileRunning=$true;trayRemovedOnExit=$true;noResidualProcesses=$true;upgradePreservesData=$true;uninstallPreservesData=$true}|ConvertTo-Json|Out-File "$report\Native_Test_Report.json" -Encoding utf8
