$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$dolphin = Join-Path $taskRoot 'work/research/dolphin/Dolphin-x64/Dolphin.exe'
$inventory = @(Get-CimInstance Win32_Process -Filter "Name='Dolphin.exe'" | Select-Object ProcessId,ExecutablePath,CommandLine)
$commands = @(Get-Command python,python3,py -ErrorAction SilentlyContinue | Select-Object Name,Source)
$libraries = @('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll','vccorlib140.dll','concrt140.dll') | ForEach-Object {
    [PSCustomObject]@{name=$_; system=Test-Path -LiteralPath (Join-Path 'C:/Windows/System32' $_); local=Test-Path -LiteralPath (Join-Path (Split-Path $dolphin -Parent) $_)}
}
[PSCustomObject]@{processes=$inventory; python=$commands; libraries=$libraries; version=(Get-Item -LiteralPath $dolphin).VersionInfo.FileVersion; executable=$dolphin} | ConvertTo-Json -Depth 4
