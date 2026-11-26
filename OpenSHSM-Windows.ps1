param(
    [string]$BuildDir,
    [string]$GameData,
    [string]$UserDir = "$env:LOCALAPPDATA\OpenSHSM",
    [switch]$CheckOnly,
    [switch]$SettingsOnly,
    [switch]$NoSettings,
    [string]$ImportImage,
    [string]$DolphinTool
)

$ErrorActionPreference = "Stop"
if (-not $BuildDir) {
    $VersionFile = Join-Path $PSScriptRoot "experiments\wii-static-recomp\BuildVersion.h"
    $VersionText = Get-Content -Raw $VersionFile
    if ($VersionText -notmatch 'OPENSHSM_RECOMP_BUILD_VERSION "([0-9.]+)"') {
        throw "BuildVersion.h differs"
    }
    $BuildDir = Join-Path $PSScriptRoot "build\$($Matches[1])\build"
}
$Launcher = Join-Path $PSScriptRoot "experiments\wii-static-recomp\launch_stock_owner_windows.py"
$Arguments = @("-B", $Launcher, "--build-dir", $BuildDir, "--user-dir", $UserDir)
if ($GameData) {
    $Arguments += @("--game-data", $GameData)
}
if ($CheckOnly) {
    $Arguments += "--check-only"
}
if ($SettingsOnly) { $Arguments += "--settings-only" }
if ($NoSettings) { $Arguments += "--no-settings" }
if ($ImportImage) { $Arguments += @("--import-image", $ImportImage) }
if ($DolphinTool) { $Arguments += @("--dolphin-tool", $DolphinTool) }

$Py = Get-Command py -ErrorAction SilentlyContinue
if ($Py) {
    & $Py.Source -3 @Arguments
} else {
    $Python = Get-Command python -ErrorAction Stop
    & $Python.Source @Arguments
}
exit $LASTEXITCODE
