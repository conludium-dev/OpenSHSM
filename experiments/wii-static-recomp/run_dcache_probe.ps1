$ErrorActionPreference = 'Stop'
$body = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'run_dolphin_probe.ps1'))
$body = $body.Replace('work/private-game/static-recomp/dolphin-coherence-probe', 'work/private-game/static-recomp/dolphin-dcache-probe')
$body = $body.Replace('$records * 736)', '($records * 736 + 64))')
$body = $body.Replace('$PSScriptRoot', ("'" + $PSScriptRoot.Replace("'", "''") + "'"))
$body = $body.Replace('$PSCommandPath', ("'" + $PSCommandPath.Replace("'", "''") + "'"))
& ([scriptblock]::Create($body)) -Mode 'boot' -Stage 'coherence' -AccurateCache 'True'
