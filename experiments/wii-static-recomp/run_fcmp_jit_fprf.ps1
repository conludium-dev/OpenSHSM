$ErrorActionPreference = 'Stop'
$body = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'run_dolphin_probe.ps1'))
$body = $body.Replace('dolphin-coherence-probe', 'dolphin-fcmp-jit-fprf')
$body = $body.Replace('$records = if ($Mode -eq ''boot'') {1} else {8}', '$records = 1024')
$body = $body.Replace('$address - 0x2000', '$address - 0x700000')
$body = $body.Replace('Dolphin.Core.CPUCore=0', 'Dolphin.Core.CPUCore=1 -C Dolphin.Core.FPRF=True')
$body = $body.Replace('$PSScriptRoot', ("'" + $PSScriptRoot.Replace("'", "''") + "'"))
$body = $body.Replace('$PSCommandPath', ("'" + $PSCommandPath.Replace("'", "''") + "'"))
& ([scriptblock]::Create($body)) -Mode 'fpr-init' -Stage 'coherence' -AccurateCache 'False'
