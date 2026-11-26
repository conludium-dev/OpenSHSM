param([ValidateSet('boot','fpr-init')][string]$Mode = 'boot', [ValidateSet('baseline','icache','coherence')][string]$Stage = 'baseline', [ValidateSet('False','True')][string]$AccurateCache = 'False')
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$probeScriptSha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
$dolphin = Join-Path $taskRoot '_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'
$private = Join-Path $taskRoot $(if ($Stage -eq 'icache') {'work/private-game/static-recomp/dolphin-icache-probe'} else {'work/private-game/static-recomp/dolphin-probe'})
if ($Stage -eq 'coherence') {$private = Join-Path $taskRoot 'work/private-game/static-recomp/dolphin-coherence-probe'}
$reportMode = if ($Stage -eq 'coherence') {$Mode + '-' + $AccurateCache.ToLower()} else {$Mode}
$taskUser = Join-Path $taskRoot '_scratch/tmp/dolphin-static-recomp-user'
if (@(Get-Process Dolphin -ErrorAction SilentlyContinue).Count) {
    throw 'Existing Dolphin process present; refusing to interfere'
}
[void](New-Item -ItemType Directory -Force -Path $taskUser)
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class DolphinProbeMemory {
    public static uint BE32(byte[] buffer, int offset) {
        return ((uint)buffer[offset] << 24) | ((uint)buffer[offset + 1] << 16) | ((uint)buffer[offset + 2] << 8) | buffer[offset + 3];
    }
    delegate bool WindowCallback(IntPtr window, IntPtr parameter);
    [DllImport("user32.dll")] static extern bool EnumWindows(WindowCallback callback, IntPtr parameter);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr window, WindowCallback callback, IntPtr parameter);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, out uint pid);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr window, System.Text.StringBuilder text, int size);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr window, uint message, IntPtr wparam, IntPtr lparam);
    [StructLayout(LayoutKind.Sequential)] struct Rectangle { public int Left,Top,Right,Bottom; }
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr window, out Rectangle rectangle);
    [DllImport("user32.dll")] static extern bool PrintWindow(IntPtr window, IntPtr dc, uint flags);
    public static void CaptureWarning(int pid, string path) {
        EnumWindows((window, parameter) => {
            uint owner;
            GetWindowThreadProcessId(window, out owner);
            var text = new System.Text.StringBuilder(256);
            GetWindowText(window, text, text.Capacity);
            Rectangle rect;
            if (owner == pid && text.ToString() == "Warning" && GetWindowRect(window, out rect)) {
                int width = rect.Right - rect.Left, height = rect.Bottom - rect.Top;
                if (width > 0 && width < 2000 && height > 0 && height < 2000) {
                    using (var bitmap = new System.Drawing.Bitmap(width, height)) {
                        using (var graphics = System.Drawing.Graphics.FromImage(bitmap)) {
                            IntPtr dc = graphics.GetHdc();
                            bool printed = PrintWindow(window, dc, 2);
                            graphics.ReleaseHdc(dc);
                            if (printed) bitmap.Save(path, System.Drawing.Imaging.ImageFormat.Png);
                        }
                    }
                }
            }
            return true;
        }, IntPtr.Zero);
    }
    public static void AcknowledgeArchitectureWarning(int pid) {
        EnumWindows((window, parameter) => {
            uint owner;
            GetWindowThreadProcessId(window, out owner);
            if (owner != pid) return true;
            bool warning = false;
            IntPtr button = IntPtr.Zero;
            EnumChildWindows(window, (child, unused) => {
                var text = new System.Text.StringBuilder(1024);
                GetWindowText(child, text, text.Capacity);
                string value = text.ToString();
                warning |= value.Contains("This build of Dolphin is not natively compiled for your CPU.");
                if (value == "OK" || value == "\u041e\u041a") button = child;
                return true;
            }, IntPtr.Zero);
            if (warning && button != IntPtr.Zero) PostMessage(button, 0xF5, IntPtr.Zero, IntPtr.Zero);
            return true;
        }, IntPtr.Zero);
    }
    public static string Windows(int pid) {
        var texts = new System.Collections.Generic.List<string>();
        WindowCallback child = (window, parameter) => {
            var text = new System.Text.StringBuilder(1024);
            GetWindowText(window, text, text.Capacity);
            if (text.Length != 0) texts.Add(text.ToString());
            return true;
        };
        EnumWindows((window, parameter) => {
            uint owner;
            GetWindowThreadProcessId(window, out owner);
            if (owner == pid) { child(window, IntPtr.Zero); EnumChildWindows(window, child, IntPtr.Zero); }
            return true;
        }, IntPtr.Zero);
        return String.Join(" | ", texts);
    }
    [StructLayout(LayoutKind.Sequential)]
    struct Region {
        public ulong Base, AllocationBase;
        public uint AllocationProtect;
        public ulong Size;
        public uint State, Protect, Type;
    }
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool ReadProcessMemory(IntPtr handle, IntPtr address, byte[] buffer, UIntPtr size, out UIntPtr read);
    [DllImport("kernel32.dll")] static extern UIntPtr VirtualQueryEx(IntPtr handle, IntPtr address, out Region region, UIntPtr size);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    public static byte[] Read(int pid, ulong address, int size) {
        IntPtr handle = OpenProcess(0x410, false, pid);
        if (handle == IntPtr.Zero) throw new Exception("OpenProcess failed");
        try {
            byte[] buffer = new byte[size];
            UIntPtr read;
            if (!ReadProcessMemory(handle, new IntPtr((long)address), buffer, (UIntPtr)size, out read) || read.ToUInt64() != (ulong)size)
                throw new Exception("ReadProcessMemory failed");
            return buffer;
        } finally { CloseHandle(handle); }
    }
    public static ulong Find(int pid, int records, bool completed) {
        IntPtr handle = OpenProcess(0x410, false, pid);
        if (handle == IntPtr.Zero) throw new Exception("OpenProcess failed");
        byte[] magic = System.Text.Encoding.ASCII.GetBytes("OSHSM_PPC_DLP001");
        try {
            ulong address = 0;
            Region region;
            while (VirtualQueryEx(handle, new IntPtr((long)address), out region, (UIntPtr)Marshal.SizeOf(typeof(Region))).ToUInt64() != 0) {
                if (region.Size == 0 || region.Base + region.Size <= address) break;
                if (region.State == 0x1000 && (region.Protect & 0x101) == 0 && region.Size >= 0x1000 && region.Size <= 0x10000000) {
                    for (ulong offset = 0; offset < region.Size; offset += 0x400000) {
                        int size = (int)Math.Min(0x400000UL, region.Size - offset);
                        byte[] buffer = new byte[size];
                        UIntPtr read;
                        if (!ReadProcessMemory(handle, new IntPtr((long)(region.Base + offset)), buffer, (UIntPtr)size, out read)) continue;
                        for (int index = 0; index + records * 736 <= (int)read.ToUInt64(); index += 4096) {
                            bool match = true;
                            for (int record = 0; record < records && match; ++record) {
                                int start = index + record * 736;
                                for (int b = 0; b < magic.Length; ++b) {
                                    if (buffer[start + b] != magic[b]) { match = false; break; }
                                }
                                if (completed) match &= buffer[start + 16] == 0xc0 && buffer[start + 17] == 1 && buffer[start + 18] == 0xca && buffer[start + 19] == 0xfe;
                            }
                            if (match) return region.Base + offset + (ulong)index;
                        }
                    }
                }
                address = region.Base + region.Size;
            }
            return 0;
        } finally { CloseHandle(handle); }
    }
}
'@
$process = $null
try {
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $dolphin
    $dol = Join-Path $private ($Mode + '.dol')
    $start.Arguments = '-b -u "' + $taskUser + '" -v Null -C Dolphin.Core.CPUCore=0 -C Dolphin.Core.DualCore=False -C Dolphin.Core.SkipIPL=True -C Dolphin.Interface.ConfirmStop=False -C Dolphin.Analytics.PermissionAsked=True -C Dolphin.Analytics.Enabled=False -C Logger.Options.WriteToFile=True -C Logger.Options.Verbosity=4 -C Logger.Logs.BOOT=True -C Logger.Logs.POWERPC=True -C Logger.Logs.CORE=True -e "' + $dol + '"'
    $start.Arguments += ' -C Dolphin.Core.AccurateCPUCache=' + $AccurateCache
    $start.UseShellExecute = $false
    $start.WorkingDirectory = Split-Path $dolphin -Parent
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    [void]$process.Start()
    Write-Output ('Started owned Dolphin PID ' + $process.Id)
    $records = if ($Mode -eq 'boot') {1} else {8}
    $address = [uint64]0
    for ($attempt = 0; $attempt -lt 80; ++$attempt) {
        if ($process.HasExited) {throw ('Dolphin exited before probe completion: ' + $process.ExitCode)}
        [DolphinProbeMemory]::AcknowledgeArchitectureWarning($process.Id)
        $address = [DolphinProbeMemory]::Find($process.Id, $records, $true)
        if ($address) {break}
        Start-Sleep -Milliseconds 500
    }
    if (!$address) {
        $incomplete = [DolphinProbeMemory]::Find($process.Id, $records, $false)
        if ($incomplete) {
            [PSCustomObject]@{status='INCOMPLETE'; hostAddress=('0x{0:X}' -f $incomplete); data=[Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$incomplete,$records*736))} |
                ConvertTo-Json | Set-Content -LiteralPath (Join-Path $private ($Mode + '-incomplete-dolphin.json')) -Encoding UTF8
            Write-Output ('Found loaded but incomplete probe at 0x{0:X}' -f $incomplete)
        }
        Write-Output ('Owned process window text: ' + [DolphinProbeMemory]::Windows($process.Id))
        [DolphinProbeMemory]::CaptureWarning($process.Id, (Join-Path $private ($Mode + '-warning.png')))
        Write-Output ('Owned process modules: ' + (($process.Modules | ForEach-Object {$_.ModuleName}) -join ','))
        throw 'No completed private PPC probe found in owned process RAM'
    }
    $bytes = [DolphinProbeMemory]::Read($process.Id, $address, $records * 736)
    $originalCode = [DolphinProbeMemory]::Read($process.Id, $address - 0x2000 + 0x210890, 0x128)
    $originalDceCode = [DolphinProbeMemory]::Read($process.Id, $address - 0x2000 + 0x212f80, 20)
    $stack = $null
    if ($Mode -eq 'boot' -and $Stage -ne 'coherence') {
        $sp = [DolphinProbeMemory]::BE32($bytes,36)
        $stack = [Convert]::ToBase64String([DolphinProbeMemory]::Read($process.Id,$address - 0x2000 + ($sp -band 0x1fffffff) - 16,64))
    }
    $report = [PSCustomObject]@{
        mode=$Mode; pid=$process.Id; hostAddress=('0x{0:X}' -f $address); records=$records; accurateCache=$AccurateCache;
        data=[Convert]::ToBase64String($bytes); originalFprCode=[Convert]::ToBase64String($originalCode); stack=$stack;
        originalDceCode=[Convert]::ToBase64String($originalDceCode);
        emulatorSha256=(Get-FileHash -LiteralPath $dolphin -Algorithm SHA256).Hash;
        harnessSha256=(Get-FileHash -LiteralPath $dol -Algorithm SHA256).Hash;
        scriptSha256=$probeScriptSha256;
        arguments=$start.Arguments; scope='Original PPC in Dolphin interpreter; private measurement adapter, no retail boot or visual acceptance'
    }
    $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $private ($reportMode + '-dolphin.json')) -Encoding UTF8
    Write-Output ('Captured ' + $records + ' completed records from owned Dolphin RAM')
} finally {
    if ($process -and !$process.HasExited) {
        $process.Kill()
        [void]$process.WaitForExit(10000)
        Write-Output ('Stopped owned Dolphin PID ' + $process.Id)
    }
}
