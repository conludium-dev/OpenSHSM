"""Exercise the actual metadata-backed ES device/kernel, not substitute services."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-es-title-boot'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
text = (experiment / 'fs_pending_device_probe.cpp').read_text().split('    for (unsigned index = 3;', 1)[0]
text = '#include "es_title_adapter.h"\n' + text
text += '''    if (kernel.open(context, "/dev/fs", 0) != 2) { return 5; }
    kernel.register_device(devices::create_es_device());
    if (kernel.open(context, "/dev/es", 0) != 3) { return 6; }
    const auto title = experiment_load_es_title(std::getenv("SHSM_ES_TMD_PATH"));
    auto* bytes = context.mmu.get_ptr(0x53ff20);
    IpcRequest es{};
    es.cmd = 7;
    es.fd = 3;
    es.req_addr = 0x135e0080;
    es.ioctl_cmd = 0x20;
    es.arg_cnt_out = 1;
    es.ioctlv_vecs.push_back({0x53ff20, 8});
    std::fill(bytes, bytes + 32, 0xa5);
    if (kernel.ioctlv(context, es) != IPC_OK) { return 7; }
    for (unsigned i = 0; i < 32; ++i) {
        if (bytes[i] != (i < 8 ? title[i] : 0xa5)) { return 8; }
    }
    unsigned refused = 0;
    for (unsigned test = 0; test < 11; ++test) {
        auto bad = es;
        std::fill(bytes, bytes + 32, 0xa5);
        try {
            if (test == 0) { bad.cmd = 6; }
            if (test == 1) { bad.fd = 99; }
            if (test == 2) { bad.req_addr += 32; }
            if (test == 3) { bad.ioctl_cmd = 0x1d; }
            if (test == 4) { bad.arg_cnt_in = 1; }
            if (test == 5) { bad.arg_cnt_out = 2; }
            if (test == 6) { bad.ioctlv_vecs.clear(); }
            if (test == 7) { bad.ioctlv_vecs[0].len = 32; }
            if (test == 8) { bad.ioctlv_vecs[0].addr += 32; }
            if (test == 9) { kernel.open(context, "/dev/es", 1); }
            else if (test == 10) { kernel.ioctl(context, bad); }
            else if (kernel.ioctlv(context, bad) != IPC_OK) { ++refused; }
        } catch (const std::runtime_error&) {
            ++refused;
        }
        if (devices::experiment_stm_pending() != pending || !pending || pending->req_addr != 0x135e0020 ||
            pending->fd != 1 || pending->ioctl_cmd != 0x1000) { return 9; }
        for (unsigned i = 0; i < 32; ++i) { if (bytes[i] != 0xa5) { return 10; } }
    }
    if (refused != 11) { return 11; }
    std::cout << "ES_TITLE_DEVICE_OUTPUT8_GUARDS24_REFUSALS11_PENDING_RETAINED\\n";
    return 0;
}
'''
host = output / 'es-title-device-probe.cpp'
host.write_text(text)
sources = [host, output / 'es_device.cpp', output / 'fs_device.cpp', output / 'stm_device.cpp',
    root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hw/mmio_dispatcher.cpp']
for path in sources[1:5]:
    assert sha(path) == build['sourceHashes'][str(path)]
exe = output / 'es-title-device-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(output),
    '-I', str(runtime / 'include'), *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'device-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
tmd_path = Path('work/private-game/disc/DATA/tmd.bin')
env['SHSM_ES_TMD_PATH'] = str(tmd_path)
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
(output / 'device-execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr
assert result.stdout.splitlines()[-1] == 'ES_TITLE_DEVICE_OUTPUT8_GUARDS24_REFUSALS11_PENDING_RETAINED'
metadata_cases = {'missing': None, 'unreadable': str(output / 'nonexistent-tmd.bin')}
data = tmd_path.read_bytes()
for label, offset in (('signature', 3), ('ios', 0x18b), ('region', 0x193)):
    bad = bytearray(data)
    bad[offset] ^= 1
    path = output / ('metadata-negative-' + label + '.bin')
    path.write_bytes(bad)
    metadata_cases[label] = str(path)
short = output / 'metadata-negative-short.bin'
short.write_bytes(data[:0x18c])
metadata_cases['short'] = str(short)
# A separate loader-only host catches refusals without crashing the component process.
loader = output / 'metadata-probe.cpp'
loader.write_text('''#include "es_title_adapter.h"
int main() {
    try { nwii::runtime::experiment_load_es_title(std::getenv("SHSM_ES_TMD_PATH")); }
    catch (const std::runtime_error&) { return 17; }
    return 0;
}
''')
loader_exe = output / 'metadata-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-I', str(output), '-I', str(runtime / 'include'),
    str(loader), '-o', str(loader_exe)], capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr[-2000:]
assert subprocess.run([str(loader_exe)], env=env, capture_output=True, timeout=10).returncode == 0
for label, path in metadata_cases.items():
    negative_env = dict(env)
    if path is None:
        del negative_env['SHSM_ES_TMD_PATH']
    else:
        negative_env['SHSM_ES_TMD_PATH'] = path
    result = subprocess.run([str(loader_exe)], env=negative_env, capture_output=True, timeout=10)
    assert result.returncode == 17 and not result.stderr, label
(output / 'device-guards.json').write_text(json.dumps({'result': 'ES_TITLE_ACTUAL_DEVICE8_GUARDS24_PENDING11_METADATA6_PASS',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'metadataRefusals': list(metadata_cases),
    'limits': ['Actual device/kernel component, not PPC lifecycle. Metadata identity checks are structural, not cryptographic.']}, indent=2) + '\n')
print('PASS actual title device output8/guards24/pending owner;11 command refusals;6 metadata refusals')
