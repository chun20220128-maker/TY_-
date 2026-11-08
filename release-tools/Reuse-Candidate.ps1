$ErrorActionPreference='Stop'
$repo=$env:GITHUB_WORKSPACE;$setup=Join-Path $repo 'output/DrillingWorkbench_Setup_1.0.4_x64.exe'
$expected='6ae7cfe1342fb062337c64e58ac04e07f310e15d3ddb8ad7a7d9e7fe6e5e2019'
if((Get-FileHash $setup -Algorithm SHA256).Hash.ToLower() -ne $expected){throw 'Pinned candidate changed'}
$stage=Join-Path $env:RUNNER_TEMP 'candidate-source-check'
& "$env:ProgramFiles\7-Zip\7z.exe" x -y $setup "-o$stage"|Out-Null
if($LASTEXITCODE -ne 0){throw 'Cannot inspect candidate'}
$src=Join-Path $repo 'release-source'
Get-ChildItem "$src\app" -Recurse -File|ForEach-Object {
 $relative=$_.FullName.Substring($src.Length+1)
 if((Get-FileHash $_.FullName -Algorithm SHA256).Hash -ne (Get-FileHash (Join-Path $stage $relative) -Algorithm SHA256).Hash){throw "Candidate product source mismatch: $relative"}
}
if((Get-FileHash "$src\drilling-workbench-blue.ico" -Algorithm SHA256).Hash -ne (Get-FileHash "$stage\drilling-workbench-blue.ico" -Algorithm SHA256).Hash){throw 'Candidate icon changed'}
if((Get-FileHash "$src\README.zh-TW.txt" -Algorithm SHA256).Hash -ne (Get-FileHash "$stage\使用說明.txt" -Algorithm SHA256).Hash){throw 'Candidate guide changed'}
Write-Host 'Pinned complete installer exactly matches final product sources; only test automation changed.'
