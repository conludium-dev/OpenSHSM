$ErrorActionPreference = 'Stop'
$base = Join-Path $PSScriptRoot 'run_dolphin_probe.ps1'
$body = [IO.File]::ReadAllText($base)
$old = 'work/private-game/static-recomp/dolphin-coherence-probe'
$new = 'work/private-game/static-recomp/dolphin-conflict-probe'
if (!$body.Contains($old)) {throw 'Probe runner routing changed'}
$body = $body.Replace($old, $new)
$body = $body.Replace('$PSScriptRoot', ("'" + $PSScriptRoot.Replace("'", "''") + "'"))
$body = $body.Replace('$PSCommandPath', ("'" + $PSCommandPath.Replace("'", "''") + "'"))
& ([scriptblock]::Create($body)) -Mode 'fpr-init' -Stage 'coherence' -AccurateCache 'True'
