$ErrorActionPreference = 'Stop'
$body = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'run_dolphin_probe.ps1'))
$body = $body.Replace('dolphin-coherence-probe', 'dolphin-spd-probe')
$body = $body.Replace('$address - 0x2000', '$address - 0x680000')
$body = $body.Replace('$PSScriptRoot', ("'" + $PSScriptRoot.Replace("'", "''") + "'"))
$body = $body.Replace('$PSCommandPath', ("'" + $PSCommandPath.Replace("'", "''") + "'"))
& ([scriptblock]::Create($body)) -Mode 'fpr-init' -Stage 'coherence' -AccurateCache 'True'
