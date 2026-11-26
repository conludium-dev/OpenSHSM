$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$output = Join-Path $root 'work/private-game/static-recomp/dolphin-es-disc'
$events = @(Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000; StartTime=(Get-Date).AddMinutes(-30)} -ErrorAction SilentlyContinue |
    Where-Object {$_.Message -match 'Dolphin'})
$rows = @()
foreach ($event in $events) {
    [xml]$xml = $event.ToXml()
    $fields = @{}
    foreach ($data in $xml.Event.EventData.Data) {$fields[$data.Name] = $data.'#text'}
    $rows += @{time=$event.TimeCreated.ToString('o'); fields=$fields}
}
$original = Join-Path $root 'work/private-game/disc/DATA/files'
$link = Join-Path $output 'DATA/files'
$report = @{events=$rows; ownedProcessStillPresent=@(Get-Process Dolphin -ErrorAction SilentlyContinue).Count;
    toolProcesses=@(Get-CimInstance Win32_Process -Filter "Name='DolphinTool.exe'" | Select-Object ProcessId,ParentProcessId,CommandLine);
    labFiles=@(Get-ChildItem -LiteralPath $link -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name);
    originalFiles=@(Get-ChildItem -LiteralPath $original | Select-Object -ExpandProperty Name)}
$runner = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'run_dolphin_probe.ps1'))
$start = $runner.IndexOf('Add-Type -ReferencedAssemblies System.Drawing')
$end = $runner.IndexOf('$process = $null', $start)
& ([scriptblock]::Create($runner.Substring($start, $end - $start)))
foreach ($tool in $report.toolProcesses) {
    $expected = Join-Path $root '_scratch/tmp/dolphin-static-recomp-lab/DolphinTool.exe'
    if ($tool.CommandLine -eq ('"' + $expected + '" --help')) {
        Write-Output ('Owned diagnostic tool window: ' + [DolphinProbeMemory]::Windows($tool.ProcessId))
        [DolphinProbeMemory]::AcknowledgeArchitectureWarning($tool.ProcessId)
        $parent = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $tool.ParentProcessId)
        if ($parent.CommandLine -match 'DolphinTool.exe' -and $parent.CommandLine -match '--help') {
            $process = Get-Process -Id $tool.ProcessId -ErrorAction SilentlyContinue
            if ($process) {
                $process.Kill()
                Write-Output ('Stopped owned blocked help-only diagnostic PID ' + $tool.ProcessId)
            }
        }
    }
}
[IO.File]::WriteAllText((Join-Path $output 'launch-diagnostics.json'), ($report | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
foreach ($row in $rows) {
    Write-Output ('Dolphin crash: app=' + $row.fields.AppName + ' module=' + $row.fields.ModuleName + ' exception=' + $row.fields.ExceptionCode)
}
Write-Output ('Dolphin processes=' + $report.ownedProcessStillPresent + ' lab file entries=' + $report.labFiles.Count + ' original entries=' + $report.originalFiles.Count)
