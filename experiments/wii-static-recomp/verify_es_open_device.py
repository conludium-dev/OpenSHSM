"""Actual ES OPEN and command refusals preserve outputs and the existing STM owner."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-es-open-boot'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
text = (experiment / 'fs_pending_device_probe.cpp').read_text().split('    for (unsigned index = 3;', 1)[0]
text += '''    if (kernel.open(context, "/dev/fs", 0) != 2) { return 5; }
    kernel.register_device(devices::create_es_device());
    if (kernel.open(context, "/dev/es", 0) != 3) { return 6; }
    auto* bytes = context.mmu.get_ptr(0x493080);
    std::fill(bytes, bytes + 32, 0xa5);
    IpcRequest es{};
    es.fd = 3;
    es.ioctl_cmd = 0x20;
    es.arg_cnt_out = 1;
    es.ioctlv_vecs.push_back({0x493080, 32});
    unsigned refused = 0;
    for (unsigned test = 0; test < 3; ++test) {
        try {
            if (test == 0) { kernel.open(context, "/dev/es", 1); }
            if (test == 1) { kernel.ioctl(context, es); }
            if (test == 2) { kernel.ioctlv(context, es); }
        } catch (const std::runtime_error&) {
            ++refused;
        }
        if (devices::experiment_stm_pending() != pending || !pending || pending->req_addr != 0x135e0020 ||
            pending->fd != 1 || pending->ioctl_cmd != 0x1000) { return 7; }
        for (unsigned i = 0; i < 32; ++i) { if (bytes[i] != 0xa5) { return 8; } }
    }
    if (refused != 3) { return 9; }
    std::cout << "ES_DEVICE_OPEN_FD3_GUARDS3_PENDING_OUTPUT_RETAINED\\n";
    return 0;
}
'''
host = output / 'es-device-probe.cpp'
host.write_text(text)
sources = [host, output / 'es_device.cpp', output / 'fs_device.cpp', output / 'stm_device.cpp',
    root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hw/mmio_dispatcher.cpp']
for path in sources[1:5]:
    assert sha(path) == build['sourceHashes'][str(path)]
exe = output / 'es-device-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(runtime / 'include'),
    *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'device-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'device-execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr and result.stdout.splitlines()[-1] == 'ES_DEVICE_OPEN_FD3_GUARDS3_PENDING_OUTPUT_RETAINED'
(output / 'device-guards.json').write_text(json.dumps({'result': 'ES_OPEN_FD3_OTHER_COMMANDS_REFUSED_OUTPUT_PENDING_UNCHANGED',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'limits': ['Actual private device/kernel component, not PPC lifecycle or original ES command equivalence; commands intentionally refuse.']}, indent=2) + '\n')
print('PASS actual ES device FD3/mode-IOCTL-IOCTLV3 refusals, pending owner/output32 retained')
