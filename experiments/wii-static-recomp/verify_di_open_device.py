"""Exercise actual DI class/shared kernel: strict OPEN, no fabricated unsupported responses."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'mass-di-open-boot'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
text = Path('experiments/wii-static-recomp/fs_pending_device_probe.cpp').read_text().split('    for (unsigned index = 3;', 1)[0]
text += '''    if (kernel.open(context, "/dev/fs", 0) != 2) { return 5; }
    kernel.register_device(devices::create_di_device());
    auto* bytes = context.mmu.get_ptr(0x493080);
    std::fill(bytes, bytes + 32, 0xa5);
    try { kernel.open(context, "/dev/di", 1); return 6; } catch (const std::runtime_error&) {}
    if (kernel.open(context, "/dev/di", 0) != 3 || kernel.open(context, "/dev/di", 0) != 4) { return 7; }
    unsigned refused = 0;
    for (unsigned test = 0; test < 9; ++test) {
        IpcRequest unverified{};
        unverified.fd = 3;
        unverified.ioctl_cmd = test == 5 ? 0x12 : test == 6 ? 0x70 : test == 7 ? 0x71 : 0x86;
        unverified.out_buf = 0x493080;
        unverified.out_size = 32;
        try {
            if (test == 0) { kernel.close(context, 3); }
            else if (test == 1) { kernel.read(context, 3, 0x493080, 32); }
            else if (test == 2) { kernel.write(context, 3, 0x493080, 32); }
            else if (test == 3) { kernel.seek(context, 3, 0, 0); }
            else if (test == 4) { kernel.ioctlv(context, unverified); }
            else { kernel.ioctl(context, unverified); }
        } catch (const std::runtime_error&) { ++refused; }
        for (unsigned i = 0; i < 32; ++i) { if (bytes[i] != 0xa5) { return 8; } }
        if (devices::experiment_stm_pending() != pending || pending->fd != 1 || pending->req_addr != 0x135e0020) { return 9; }
    }
    if (refused != 9 || kernel.close(context, 99) != -4) { return 10; }
    std::cout << "DI_SHARED_KERNEL_FDS3_4_BAD_MODE_UNVERIFIED9_PENDING_BYTES_PASS\\n";
    return 0;
}
'''
host = output / 'di-device-probe.cpp'
host.write_text('#include <algorithm>\n' + text)
sources = [host, output / 'di_device.cpp', output / 'fs_device.cpp', output / 'stm_device.cpp',
    root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hw/mmio_dispatcher.cpp']
for source in sources[1:]:
    assert sha(source) == build['sourceHashes'][str(source)]
exe = output / 'di-device-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(runtime / 'include'),
    *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'device-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'device-execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
assert result.stdout.splitlines()[-1] == 'DI_SHARED_KERNEL_FDS3_4_BAD_MODE_UNVERIFIED9_PENDING_BYTES_PASS'
(output / 'device-guards.json').write_text(json.dumps({'result': 'ACTUAL_DI_SHARED_KERNEL_OPEN_BAD_MODE_UNVERIFIED9_PENDING_BYTES_PASS',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'limits': ['Component refusal tests do not verify original DI ioctl behavior; commands intentionally stop before mutation.']}, indent=2) + '\n')
print('PASS actual DI/shared kernel FDs3-4/bad mode/nine unsupported commands refused/pending STM and bytes retained')
