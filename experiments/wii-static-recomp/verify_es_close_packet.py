"""Exercise the actual CLOSE packet adapter/kernel and refusal before mutation."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-es-close-boot'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
text = '#include "es_close_adapter.h"\n' + (experiment / 'fs_pending_device_probe.cpp').read_text().split('    for (unsigned index = 3;', 1)[0]
text += '''    if (kernel.open(context, "/dev/fs", 0) != 2) { return 5; }
    kernel.register_device(devices::create_es_device());
    if (kernel.open(context, "/dev/es", 0) != 3) { return 6; }
    auto* packet = context.mmu.get_ptr(0x135e0080);
    auto* output = context.mmu.get_ptr(0x493080);
    const std::array<uint32_t, 8> expected{2, 0, 3, 0x1d, 1, 1, 0x80540010, 0};
    unsigned refused = 0;
    for (unsigned test = 0; test < 10; ++test) {
        std::fill(packet, packet + 64, 0);
        std::fill(output, output + 32, 0xa5);
        for (unsigned index = 0; index < expected.size(); ++index) {
            experiment_ipc_store_be32(packet + index * 4, expected[index]);
        }
        if (test < 8) { packet[test * 4 + 3] ^= 1; }
        const std::vector<uint8_t> before(packet, packet + 64);
        bool rejected = false;
        try { experiment_es_close_dispatch(context, test == 8 ? 0x135e00a0 : 0x135e0080); }
        catch (const std::runtime_error&) { rejected = true; }
        if (test < 9) {
            if (!rejected || !std::equal(before.begin(), before.end(), packet)) { return 7; }
            ++refused;
        } else {
            if (rejected || experiment_ipc_be32(packet) != 8 || experiment_ipc_be32(packet + 4) != 0 ||
                experiment_ipc_be32(packet + 8) != 2) { return 8; }
            for (unsigned index = 12; index < 64; ++index) { if (packet[index] != before[index]) { return 9; } }
        }
        if (devices::experiment_stm_pending() != pending || !pending || pending->req_addr != 0x135e0020 ||
            pending->fd != 1 || pending->ioctl_cmd != 0x1000) { return 10; }
        for (unsigned index = 0; index < 32; ++index) { if (output[index] != 0xa5) { return 11; } }
    }
    if (refused != 9 || kernel.close(context, 3) != -4 || kernel.open(context, "/dev/es", 0) != 3) { return 12; }
    std::cout << "ES_CLOSE_PACKET_REFUSALS9_RELEASE_REUSE_FD3_PENDING_OUTPUT_RETAINED" << std::endl;
    return 0;
}
'''
host = output / 'es-close-packet-probe.cpp'
host.write_text(text)
sources = [host, output / 'es_device.cpp', output / 'fs_device.cpp', output / 'stm_device.cpp',
    root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hw/mmio_dispatcher.cpp']
for path in sources[1:5]:
    assert sha(path) == build['sourceHashes'][str(path)]
exe = output / 'es-close-packet-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(output),
    '-I', str(runtime / 'include'), *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'packet-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
(output / 'packet-execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr
assert result.stdout.splitlines()[-1] == 'ES_CLOSE_PACKET_REFUSALS9_RELEASE_REUSE_FD3_PENDING_OUTPUT_RETAINED'
(output / 'packet-guards.json').write_text(json.dumps({'result': 'ACTUAL_CLOSE_PACKET9_REFUSALS_RELEASE_REUSE_PENDING_PASS',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'limits': ['Actual packet adapter/kernel/device component, not SDK thread/control-flow or physical-Wii behavior.']}, indent=2) + '\n')
print('PASS actual CLOSE packet9 refusals preserve packet/output/STM; valid release and FD3reuse')
