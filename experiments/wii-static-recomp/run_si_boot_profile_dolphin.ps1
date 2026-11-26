$ErrorActionPreference = 'Stop'
$body = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'run_dolphin_probe.ps1'))
$body = $body.Replace('dolphin-coherence-probe', 'dolphin-si-boot-profile')
$body = $body.Replace('dolphin-static-recomp-user', 'dolphin-si-boot-profile-user')
$body = $body.Replace('$records = if ($Mode -eq ''boot'') {1} else {8}', '$records = 16')
$body = $body.Replace('$address - 0x2000', '$address - 0x680000')
$body = $body.Replace('originalDceCode=[Convert]::ToBase64String($originalDceCode);', 'originalDceCode=[Convert]::ToBase64String($originalDceCode); vectorCode=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x500,152));')
$body = $body.Replace(' -C Dolphin.Core.AccurateCPUCache=', ' -C Dolphin.Core.SIDevice0=0 -C Dolphin.Core.SIDevice1=0 -C Dolphin.Core.SIDevice2=0 -C Dolphin.Core.SIDevice3=0 -C Dolphin.Core.AccurateCPUCache=')
$body = $body.Replace('$PSScriptRoot', ("'" + $PSScriptRoot.Replace("'", "''") + "'"))
$body = $body.Replace('$PSCommandPath', ("'" + $PSCommandPath.Replace("'", "''") + "'"))
& ([scriptblock]::Create($body)) -Mode 'fpr-init' -Stage 'coherence' -AccurateCache 'True'
