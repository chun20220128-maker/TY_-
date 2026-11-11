$ErrorActionPreference='Stop'
New-Item verification -ItemType Directory -Force|Out-Null
$report=@{startedAt=(Get-Date).ToUniversalTime().ToString('o');os=[Environment]::OSVersion.VersionString;sha256=(Get-FileHash candidate/DrillingWorkbench_Setup_1.0.5_x64.exe -Algorithm SHA256).Hash.ToLower();result='not-completed';scans=@()}
try {
  $status=Get-MpComputerStatus
  $report.defenderBefore=$status|Select-Object AMEngineVersion,AMProductVersion,AntivirusSignatureVersion,AntivirusSignatureLastUpdated,AntivirusEnabled,AMServiceEnabled
  try{Update-MpSignature;$report.signatureUpdate='success'}catch{$report.signatureUpdate=$_.Exception.Message}
  $mp=Get-ChildItem "$env:ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe" -ErrorAction SilentlyContinue|Sort-Object FullName -Descending|Select-Object -First 1
  if(!$mp){$mp=Get-Item "$env:ProgramFiles\Windows Defender\MpCmdRun.exe"}
  $extract=Join-Path $env:RUNNER_TEMP 'workbench-av-payload';New-Item $extract -ItemType Directory -Force|Out-Null
  & 7z x candidate/DrillingWorkbench_Setup_1.0.5_x64.exe "-o$extract" -y | Out-File verification/extract.log
  if($LASTEXITCODE -ne 0){throw 'Payload extraction failed'}
  foreach($path in @((Resolve-Path candidate/DrillingWorkbench_Setup_1.0.5_x64.exe).Path,$extract)){
    $output=& $mp.FullName -Scan -ScanType 3 -File $path -DisableRemediation 2>&1
    $code=$LASTEXITCODE
    $report.scans+=@{path=$path;exitCode=$code;output=($output|Out-String)}
    if($code -ne 0){throw "Defender scan did not return clean success: $code"}
  }
  $report.defenderAfter=Get-MpComputerStatus|Select-Object AMEngineVersion,AntivirusSignatureVersion,AntivirusSignatureLastUpdated,AntivirusEnabled,AMServiceEnabled
  if(!$report.defenderAfter.AntivirusEnabled){throw 'Antivirus not enabled'}
  $report.result='no-threats-detected'
}catch{$report.error=$_.Exception.Message;Write-Warning $_}
finally{$report.completedAt=(Get-Date).ToUniversalTime().ToString('o');$report|ConvertTo-Json -Depth 8|Out-File verification/Defender_Scan_Report.json -Encoding utf8}
# An unavailable scanner is recorded honestly; native compatibility tests still run.
