$ErrorActionPreference = 'Stop'
$base = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'run_dolphin_probe.ps1'))
$base = $base.Replace('dolphin-coherence-probe', 'dolphin-es-datadir-disc')
$base = $base.Replace('dolphin-static-recomp-user', 'dolphin-es-datadir-disc-user')
$base = $base.Replace('$records = if ($Mode -eq ''boot'') {1} else {8}', '$records = 16')
$base = $base.Replace('$address - 0x2000', '$address - 0x680000')
$base = $base.Replace('$dol = Join-Path $private ($Mode + ''.dol'')', '$dol = Join-Path $private ''DATA/sys/main.dol''')
$base = $base.Replace('originalDceCode=[Convert]::ToBase64String($originalDceCode);', 'originalDceCode=[Convert]::ToBase64String($originalDceCode); vectorCode=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x500,152));')
$base = $base.Replace(' -C Dolphin.Core.AccurateCPUCache=', ' -C Logger.Logs.IOS_ES=True -C Logger.Logs.DVDINTERFACE=True -C Dolphin.Core.AccurateCPUCache=')
$base = $base.Replace('$PSScriptRoot', ("'" + $PSScriptRoot.Replace("'", "''") + "'"))
$base = $base.Replace('$PSCommandPath', ("'" + $PSCommandPath.Replace("'", "''") + "'"))
& ([scriptblock]::Create($base)) -Mode 'fpr-init' -Stage 'coherence' -AccurateCache 'True'
