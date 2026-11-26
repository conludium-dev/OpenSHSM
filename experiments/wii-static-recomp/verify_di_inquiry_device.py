"""Check actual DI/shared-kernel inquiry and unsupported/source refusal atomicity."""
from pathlib import Path
import base64
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'di-inquiry-device'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
preparation = json.loads((output / 'preparation.json').read_text())
assert preparation['preparerSha256'] == sha(experiment / 'prepare_di_inquiry_device.py')
for path, digest in {**preparation['sourceHashes'], **preparation['headerHashes']}.items():
    assert sha(Path(path)) == digest
text = (experiment / 'fs_pending_device_probe.cpp').read_text().split('    for (unsigned index = 3;', 1)[0]
text = ('#include "di_inquiry_adapter.h"\n' + text).replace('int main() {', 'int main(int argc, char** argv) {')
text += r'''    if (kernel.open(context, "/dev/fs", 0) != 2) { return 5; }
    kernel.register_device(devices::create_di_device());
    if (kernel.open(context, "/dev/di", 0) != 3) { return 6; }
    auto* input = context.mmu.get_ptr(0x135e2580);
    std::fill(input, input + 32, 0);
    input[0] = 0x12;
    auto* guarded = context.mmu.get_ptr(0x492240);
    std::fill(guarded, guarded + 96, 0xa5);
    IpcRequest inquiry{};
    inquiry.cmd = 6; inquiry.fd = 3; inquiry.req_addr = 0x135e00e0; inquiry.ioctl_cmd = 0x12;
    inquiry.in_buf = 0x135e2580; inquiry.in_size = 32; inquiry.out_buf = 0x492260; inquiry.out_size = 32;
    if (argc > 1) {
        try { kernel.ioctl(context, inquiry); return 7; } catch (const std::runtime_error&) {}
        for (unsigned i = 0; i < 96; ++i) { if (guarded[i] != 0xa5) { return 8; } }
        if (devices::experiment_stm_pending() != pending) { return 9; }
        return 17;
    }
    if (kernel.ioctl(context, inquiry) != 1) { return 10; }
    std::cout << "DI_INQUIRY_BYTES";
    for (unsigned i = 0; i < 32; ++i) { std::cout << ' ' << unsigned(guarded[32 + i]); }
    std::cout << '\n';
    for (unsigned i = 0; i < 96; ++i) { if ((i < 32 || i >= 64) && guarded[i] != 0xa5) { return 11; } }
    unsigned refused = 0;
    for (unsigned test = 0; test < 13; ++test) {
        auto bad = inquiry;
        std::fill(guarded, guarded + 96, 0xa5);
        if (test == 0) { bad.cmd = 7; }
        if (test == 1) { bad.fd = 99; }
        if (test == 2) { bad.req_addr += 32; }
        if (test == 3) { bad.ioctl_cmd = 0x70; }
        if (test == 4) { bad.in_buf += 32; }
        if (test == 5) { bad.in_size = 31; }
        if (test == 6) { bad.out_buf += 32; }
        if (test == 7) { bad.out_size = 31; }
        if (test == 8) { bad.out_size = 33; }
        if (test == 9) { input[0] ^= 1; }
        if (test == 10) { input[31] ^= 1; }
        try {
            if (test == 11) { kernel.ioctlv(context, bad); }
            else if (test == 12) { kernel.read(context, 3, 0x492260, 32); }
            else if (kernel.ioctl(context, bad) != 1) { ++refused; }
        } catch (const std::runtime_error&) { ++refused; }
        if (test == 9) { input[0] ^= 1; }
        if (test == 10) { input[31] ^= 1; }
        for (unsigned i = 0; i < 96; ++i) { if (guarded[i] != 0xa5) { return 12; } }
        if (devices::experiment_stm_pending() != pending || pending->req_addr != 0x135e0020 || pending->fd != 1) { return 13; }
    }
    IpcRequest legacy{};
    legacy.cmd = 6; legacy.fd = 3; legacy.req_addr = 0x135e0080; legacy.ioctl_cmd = 0x86;
    legacy.in_buf = 0x135e2560; legacy.in_size = 32;
    auto* command = context.mmu.get_ptr(legacy.in_buf);
    std::fill(command, command + 32, 0); command[0] = 0x86;
    if (refused != 13 || kernel.ioctl(context, legacy) != 1) { return 14; }
    std::cout << "DI_INQUIRY_SHARED_KERNEL_OUTPUT32_GUARDS64_REFUSALS13_LEGACY86_PENDING_PASS\n";
    return 0;
}
'''
host = output / 'device-probe.cpp'
host.write_text(text)
sources = [host, output / 'di_device.cpp', output / 'fs_device.cpp', output / 'stm_device.cpp',
    root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hw/mmio_dispatcher.cpp']
exe = output / 'device-probe'
compiled = subprocess.run(['clang++', '-std=c++20', '-O0', '-I', str(output), '-I', str(runtime / 'include'),
    *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-2500:]
env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
metadata_path = output / 'dolphin-lab-inquiry.bin'
env['SHSM_DI_LAB_INQUIRY_PATH'] = str(metadata_path)
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
(output / 'execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
line = next(line for line in result.stdout.splitlines() if line.startswith('DI_INQUIRY_BYTES '))
actual = bytes(map(int, line.split()[1:]))
capture = json.loads((root / 'dolphin-es-di-ticket-events-disc/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
assert actual == base64.b64decode(capture['inquiryPhysical'])
data = metadata_path.read_bytes()
cases = {'missing': None, 'empty': '', 'absent': str(output / 'absent.bin'), 'directory': str(output)}
for label, blob in [('short', data[:-1]), ('long', data + b'\0'), ('huge', data + bytes(65536))]:
    path = output / (label + '-metadata.bin')
    path.write_bytes(blob)
    cases[label] = str(path)
for label, offset in [('revision', 3), ('date', 7), ('model', 11), ('tail', 31)]:
    blob = bytearray(data)
    blob[offset] ^= 1
    path = output / (label + '-metadata.bin')
    path.write_bytes(blob)
    cases[label] = str(path)
for label, path in cases.items():
    negative_env = dict(env)
    if path is None:
        del negative_env['SHSM_DI_LAB_INQUIRY_PATH']
    else:
        negative_env['SHSM_DI_LAB_INQUIRY_PATH'] = path
    result = subprocess.run([str(exe), 'negative'], env=negative_env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 17 and not result.stderr, label
(output / 'device-verification.json').write_text(json.dumps({'result': 'ACTUAL_DI_INQUIRY_KERNEL_LAB32_ORIGINAL_MATCH_PASS',
    'verifierSha256': sha(Path(__file__)), 'preparationSha256': sha(output / 'preparation.json'),
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'requestRefusals': 13, 'metadataRefusals': list(cases),
    'limits': ['Actual kernel/DI class; result1/output32 original LAB match, guard64 and pendingSTM preserved.',
        'LAB emulator drive metadata, not physical Wii identity or game asset/public import requirement.',
        'Component test not guest callback/free/cache or complete native inquiry.']}, indent=2) + '\n')
print('PASS actual DI/shared kernel reply1/output32 originalLABmatch/guard64/13request-11source refusals/legacy86/pendingSTM')
