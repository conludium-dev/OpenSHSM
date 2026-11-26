"""Actual shared-kernel file OPEN; bad lab files/modes and unverified operations refuse."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-sysconf-open-boot'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
lab = Path('_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF')
assert sha(lab) == build['laboratoryConsoleFileSha256']
data = lab.read_bytes()
for name, content in [('short', data[:-1]), ('head', b'BAD!' + data[4:]), ('tail', data[:-4] + b'BAD!')]:
    (output / ('invalid-' + name + '.bin')).write_bytes(content)
text = (experiment / 'fs_pending_device_probe.cpp').read_text().split('    for (unsigned index = 3;', 1)[0]
text = text.replace('int main() {', 'int main(int argc, char** argv) {\n    if (argc != 5) { return 1; }')
text += '''    if (kernel.open(context, "/dev/fs", 0) != 2) { return 5; }
    auto* bytes = context.mmu.get_ptr(0x493080);
    std::fill(bytes, bytes + 32, 0xa5);
    unsigned refused = 0;
    for (unsigned test = 0; test < 8; ++test) {
        unsetenv("SHSM_SC_LAB_FILE");
        if (test == 1) { setenv("SHSM_SC_LAB_FILE", "", 1); }
        if (test == 2) { setenv("SHSM_SC_LAB_FILE", "_scratch/tmp/openshsm-no-such-console-file", 1); }
        if (test >= 3 && test <= 5) { setenv("SHSM_SC_LAB_FILE", argv[test - 1], 1); }
        if (test >= 6) { setenv("SHSM_SC_LAB_FILE", argv[1], 1); }
        try {
            kernel.open(context, test == 7 ? "/shared2/sys/UNKNOWN" : "/shared2/sys/SYSCONF", test == 6 ? 0 : 1);
        } catch (const std::runtime_error&) { ++refused; }
        if (devices::experiment_stm_pending() != pending || !pending || pending->req_addr != 0x135e0020) { return 6; }
        for (unsigned i = 0; i < 32; ++i) { if (bytes[i] != 0xa5) { return 7; } }
    }
    if (refused != 8) { return 8; }
    setenv("SHSM_SC_LAB_FILE", argv[1], 1);
    if (kernel.open(context, "/shared2/sys/SYSCONF", 1) != 3) { return 9; }
    for (unsigned test = 0; test < 4; ++test) {
        try {
            if (test == 0) { kernel.open(context, "/shared2/sys/SYSCONF", 1); }
            if (test == 1) { kernel.read(context, 3, 0x493080, 32); }
            if (test == 2) { kernel.close(context, 3); }
            if (test == 3) { kernel.write(context, 3, 0x493080, 32); }
        } catch (const std::runtime_error&) { ++refused; }
        if (devices::experiment_stm_pending() != pending) { return 10; }
        for (unsigned i = 0; i < 32; ++i) { if (bytes[i] != 0xa5) { return 11; } }
    }
    if (refused != 12) { return 12; }
    std::cout << "SYSCONF_SHARED_KERNEL_FD3_GUARDS12_PENDING_OUTPUT_RETAINED\\n";
    return 0;
}
'''
host = output / 'sysconf-device-probe.cpp'
host.write_text('#include <algorithm>\n#include <cstdlib>\n' + text)
sources = [host, output / 'fs_device.cpp', output / 'stm_device.cpp', root / 'stm-open-native/ios_kernel.cpp',
    runtime / 'src/hw/mmio_dispatcher.cpp']
for source in sources[1:4]:
    assert sha(source) == build['sourceHashes'][str(source)]
exe = output / 'sysconf-device-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(runtime / 'include'),
    *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'device-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
result = subprocess.run([str(exe), str(lab), *[str(output / ('invalid-' + name + '.bin')) for name in ('short', 'head', 'tail')]],
    env=env, capture_output=True, text=True, timeout=30)
(output / 'device-execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
assert result.stdout.splitlines()[-1] == 'SYSCONF_SHARED_KERNEL_FD3_GUARDS12_PENDING_OUTPUT_RETAINED'
(output / 'device-guards.json').write_text(json.dumps({'verifierSha256': sha(Path(__file__)),
    'buildSha256': sha(output / 'build.json'), 'sourceHashes': {str(source): sha(source) for source in sources},
    'executableSha256': sha(exe), 'result': 'SHARED_FD3_REAL_LAB_FILE_OPEN_12_REFUSALS_PENDING_OUTPUT_RETAINED',
    'limits': ['Only private laboratory read-only OPEN; other operations intentionally refuse, not physical Wii evidence.']}, indent=2) + '\n')
print('PASS actual FS/kernel/lab-file FD3;12 malformed-file/mode/path/duplicate/unverified-operation refusals;STM/output retained')
