param([switch]$Unobserved)
$ErrorActionPreference = 'Stop'
$body = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'run_dolphin_probe.ps1'))
$privateName = if ($Unobserved) {'dolphin-sram-unobserved'} else {'dolphin-sram'}
$body = $body.Replace('dolphin-coherence-probe', $privateName)
$body = $body.Replace('dolphin-static-recomp-user', 'dolphin-sram-user')
$body = $body.Replace('$records = if ($Mode -eq ''boot'') {1} else {8}', '$records = 16')
$body = $body.Replace('$address - 0x2000', '$address - 0x680000')
$body = $body.Replace(' -C Dolphin.Core.AccurateCPUCache=', ' -C Dolphin.Core.SerialPort1=255 -C Dolphin.Core.AccurateCPUCache=')
$body = $body.Replace('$PSScriptRoot', ("'" + $PSScriptRoot.Replace("'", "''") + "'"))
$body = $body.Replace('$PSCommandPath', ("'" + $PSCommandPath.Replace("'", "''") + "'"))
& ([scriptblock]::Create($body)) -Mode 'fpr-init' -Stage 'coherence' -AccurateCache 'True'
