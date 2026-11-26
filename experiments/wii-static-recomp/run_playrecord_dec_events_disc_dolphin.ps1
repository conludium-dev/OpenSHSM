$ErrorActionPreference = 'Stop'
$base = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'run_dolphin_probe.ps1'))
$base = $base.Replace('dolphin-coherence-probe', 'dolphin-playrecord-dec-events-disc')
$base = $base.Replace('dolphin-static-recomp-user', 'dolphin-playrecord-dec-events-disc-user')
$base = $base.Replace('$records = if ($Mode -eq ''boot'') {1} else {8}', '$records = 16')
$base = $base.Replace('$address - 0x2000', '$address - 0x680000')
$base = $base.Replace('$dol = Join-Path $private ($Mode + ''.dol'')', '$dol = Join-Path $private ''DATA/sys/main.dol''')
$base = $base.Replace('originalDceCode=[Convert]::ToBase64String($originalDceCode);', 'originalDceCode=[Convert]::ToBase64String($originalDceCode); confPhysical=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x4b31a0,0x4000)); productPhysical=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x3800,256)); inquiryPhysical=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x492260,32)); ticketViewPhysical=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x6f4000,216)); ticketScalarsPhysical=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x6f4200,8)); consumptionCountPhysical=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x6f4220,32)); consumptionScalarsPhysical=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x6f4240,32)); closeScalarsPhysical=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x6f4260,32)); events=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x740000,0x50040)); playrecordStartScalars=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x6f4280,64)); playrecordBufferPhysical=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x493120,128)); playrecordFileInfoPhysical=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x680000 + 0x4931d0,140));')
$base = $base.Replace(' -C Dolphin.Core.AccurateCPUCache=', ' -C Logger.Logs.IOS_DI=True -C Logger.Logs.IOS_ES=True -C Logger.Logs.IOS_FS=True -C Logger.Logs.IOS=True -C Dolphin.Core.AccurateCPUCache=')
$base = $base.Replace('$PSScriptRoot', ("'" + $PSScriptRoot.Replace("'", "''") + "'"))
$base = $base.Replace('$PSCommandPath', ("'" + $PSCommandPath.Replace("'", "''") + "'"))
& ([scriptblock]::Create($base)) -Mode 'fpr-init' -Stage 'coherence' -AccurateCache 'True'
$captureTaskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$capturePath = Join-Path $captureTaskRoot 'work/private-game/static-recomp/dolphin-playrecord-dec-events-disc/fpr-init-true-dolphin.json'
$capture = [IO.File]::ReadAllText($capturePath) | ConvertFrom-Json
$labPath = Join-Path $captureTaskRoot '_scratch/tmp/dolphin-playrecord-dec-events-disc-user/Wii/title/00000001/00000002/data/play_rec.dat'
$capture | Add-Member -NotePropertyName playrecordLabFile -NotePropertyValue ([Convert]::ToBase64String([IO.File]::ReadAllBytes($labPath)))
$capture | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $capturePath -Encoding UTF8
Write-Output 'Captured LAB file after owned Dolphin cleanup'
