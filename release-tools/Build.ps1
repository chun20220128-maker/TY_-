$ErrorActionPreference='Stop'
$repo=$env:GITHUB_WORKSPACE;$source=Join-Path $repo 'release-tools';$inputSetup=Join-Path $env:RUNNER_TEMP 'base.exe'
$expected='fb9f7f9f668ae038ebba5d3feda29892daf808c721cca4189a9369aa3a4a4869'
Invoke-WebRequest 'https://github.com/chun20220128-maker/TY_-/releases/download/drilling-desktop-v1.0.3/DrillingWorkbench_Setup_1.0.3_x64.exe' -OutFile $inputSetup
if((Get-FileHash $inputSetup -Algorithm SHA256).Hash.ToLower() -ne $expected){throw 'Base installer checksum mismatch'}
$stage=Join-Path $env:RUNNER_TEMP 'payload'
& "$env:ProgramFiles\7-Zip\7z.exe" x -y $inputSetup "-o$stage" | Out-Null
if($LASTEXITCODE -ne 0){throw 'Base extraction failed'}
$manifest=Get-Content "$stage\release-manifest.json" -Raw -Encoding utf8|ConvertFrom-Json -AsHashtable
foreach($name in $manifest.files.Keys){if((Get-FileHash (Join-Path $stage $name) -Algorithm SHA256).Hash.ToLower() -ne $manifest.files[$name]){throw "Input payload mismatch: $name"}}
Copy-Item "$repo\release-source\app\*" "$stage\app" -Recurse -Force
Copy-Item "$repo\release-source\drilling-workbench-blue.ico" "$stage\drilling-workbench-blue.ico" -Force
Copy-Item "$repo\release-source\README.zh-TW.txt" "$stage\使用說明.txt" -Force
Copy-Item "$repo\release-source\README.zh-TW.txt" "$stage\README.zh-TW.txt" -Force
$build=Join-Path $env:RUNNER_TEMP 'native-build';New-Item $build -ItemType Directory|Out-Null
$vs=& "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars=Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'
$command='"'+$vcvars+'" && rc /nologo /c 65001 /fo "'+$build+'\launcher.res" "'+$source+'\launcher.rc" && cl /nologo /utf-8 /O2 /MT /Fe:"'+$build+'\DrillingWorkbench.exe" /Fo"'+$build+'\launcher.obj" "'+$source+'\launcher.c" "'+$build+'\launcher.res" /link /SUBSYSTEM:WINDOWS /INCREMENTAL:NO shell32.lib user32.lib'
Push-Location $stage
try{& $env:ComSpec /d /s /c $command;if($LASTEXITCODE -ne 0){throw 'Native launcher compilation failed'}}finally{Pop-Location}
Copy-Item "$build\DrillingWorkbench.exe" "$stage\鑽探工作台.exe" -Force
Copy-Item "$build\DrillingWorkbench.exe" "$stage\DrillingWorkbench.exe" -Force
$manifest.release='Windows-offline-installer-v1.0.4';$manifest.projectPersistence='session-memory-only; explicit JSON export';$manifest.historyPersistence='local SQLite';$manifest.networkRequired=$false
$manifest.files=@{}
foreach($folder in @('app','runtime','browser','data')){
 Get-ChildItem (Join-Path $stage $folder) -Recurse -File|Where-Object {$_.FullName -notmatch '__pycache__|\.pyc$'}|ForEach-Object {$name=$_.FullName.Substring($stage.Length+1);$manifest.files[$name]=(Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()}
}
foreach($name in @('鑽探工作台.exe','drilling-workbench-blue.ico','使用說明.txt','THIRD-PARTY-NOTICES.txt','MINGW-LICENSE.txt','CHROMIUM-LICENSE.txt')){$manifest.files[$name]=(Get-FileHash (Join-Path $stage $name) -Algorithm SHA256).Hash.ToLower()}
[IO.File]::WriteAllText("$stage\release-manifest.json",($manifest|ConvertTo-Json -Depth 20),[Text.UTF8Encoding]::new($false))
$makensis="${env:ProgramFiles(x86)}\NSIS\makensis.exe"
if(!(Test-Path $makensis)){choco install nsis --yes --no-progress --limit-output;if($LASTEXITCODE -ne 0){throw 'NSIS install failed'}}
$out=Join-Path $repo 'output';New-Item $out -ItemType Directory|Out-Null
$setup=Join-Path $out 'DrillingWorkbench_Setup_1.0.4_x64.exe'
& $makensis /V3 /INPUTCHARSET UTF8 "/DSTAGE=$stage" "/DOUTPUT=$setup" "$source\installer.nsi"
if($LASTEXITCODE -ne 0 -or !(Test-Path $setup)){throw 'Installer compilation failed'}
$sha=(Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()
"$sha  DrillingWorkbench_Setup_1.0.4_x64.exe" | Out-File "$out\SHA256SUMS.txt" -Encoding utf8
@{version='1.0.4';sha256=$sha;bytes=(Get-Item $setup).Length;inputInstallerSHA256=$expected;historyProjects=14;historyPrices=322;build='Native Windows MSVC and NSIS';networkRequired=$false;projectPersistence='RAM only; explicit export';tray='shown only while running'}|ConvertTo-Json|Out-File "$out\Build_Report.json" -Encoding utf8
Copy-Item "$stage\使用說明.txt" "$out\使用說明.txt"
python -m pip install --disable-pip-version-check pefile==2024.8.26
python "$source\verify-windows-icons.py" --icon "$stage\drilling-workbench-blue.ico" $setup "$stage\鑽探工作台.exe" | Out-File "$out\Icon_Verification.json" -Encoding utf8
if($LASTEXITCODE -ne 0){throw 'Embedded icon verification failed'}
