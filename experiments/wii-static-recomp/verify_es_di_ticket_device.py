"""Exercise actual shared kernel/ES class, full original view and refusal atomicity."""
from pathlib import Path
import base64
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'es-di-ticket-device'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
preparation = json.loads((output / 'preparation.json').read_text())
assert preparation['preparerSha256'] == sha(experiment / 'prepare_es_di_ticket_device.py')
assert preparation['adapterSha256'] == sha(experiment / 'es_di_ticket_adapter.h')
for path, digest in {**preparation['sourceHashes'], **preparation['headerHashes']}.items():
    assert sha(Path(path)) == digest
text = (experiment / 'fs_pending_device_probe.cpp').read_text().split('    for (unsigned index = 3;', 1)[0]
text = ('#include "es_di_ticket_adapter.h"\n#include <algorithm>\n' + text).replace('int main() {', 'int main(int argc, char** argv) {')
text += r'''    if (kernel.open(context, "/dev/fs", 0) != 2) { return 5; }
    kernel.register_device(devices::create_es_device());
    const bool legacy = argc > 1 && std::string(argv[1]) == "legacy";
    if (legacy) {
        if (kernel.open(context, "/dev/es", 0) != 3) { return 6; }
        auto* bytes = context.mmu.get_ptr(0x53ff20);
        std::fill(bytes, bytes + 32, 0xa5);
        IpcRequest title{};
        title.cmd = 7; title.fd = 3; title.req_addr = 0x135e0080; title.ioctl_cmd = 0x20;
        title.arg_cnt_out = 1; title.ioctlv_vecs.push_back({0x53ff20, 8});
        if (kernel.ioctlv(context, title) != IPC_OK) { return 7; }
        const auto expected = experiment_load_es_title(std::getenv("SHSM_ES_TMD_PATH"));
        for (unsigned i = 0; i < 32; ++i) { if (bytes[i] != (i < 8 ? expected[i] : 0xa5)) { return 8; } }
        std::cout << "LEGACY_ES_TITLE_FD3_OUTPUT8_GUARDS24_PASS\n";
        return 0;
    }
    kernel.register_device(devices::create_di_device());
    if (kernel.open(context, "/dev/di", 0) != 3 || kernel.open(context, "/dev/es", 0) != 4) { return 9; }
    auto* guarded = context.mmu.get_ptr(0x53ff60);
    std::fill(guarded, guarded + 280, 0xa5);
    IpcRequest view{};
    view.cmd = 7; view.fd = 4; view.req_addr = 0x135e0080; view.ioctl_cmd = 0x1b;
    view.arg_cnt_in = 1; view.arg_cnt_out = 1;
    view.ioctlv_vecs.push_back({0, 0}); view.ioctlv_vecs.push_back({0x53ff80, 216});
    if (argc > 1 && std::string(argv[1]) == "negative") {
        try { kernel.ioctlv(context, view); return 10; } catch (const std::runtime_error&) {}
        for (unsigned i = 0; i < 280; ++i) { if (guarded[i] != 0xa5) { return 11; } }
        if (devices::experiment_stm_pending() != pending) { return 12; }
        std::cout << "TICKET_SOURCE_REFUSED_WITHOUT_OUTPUT_MUTATION\n";
        return 17;
    }
    if (kernel.ioctlv(context, view) != IPC_OK) { return 13; }
    std::cout << "ES_DI_TICKET_BYTES";
    for (unsigned i = 0; i < 216; ++i) { std::cout << ' ' << unsigned(guarded[32 + i]); }
    std::cout << '\n';
    for (unsigned i = 0; i < 280; ++i) { if ((i < 32 || i >= 248) && guarded[i] != 0xa5) { return 14; } }
    const auto original = *pending;
    unsigned refused = 0;
    for (unsigned test = 0; test < 16; ++test) {
        auto bad = view;
        std::fill(guarded, guarded + 280, 0xa5);
        if (test == 0) { bad.cmd = 6; }
        if (test == 1) { bad.fd = 99; }
        if (test == 2) { bad.fd = 3; }
        if (test == 3) { bad.req_addr += 32; }
        if (test == 4) { bad.ioctl_cmd = 0x20; }
        if (test == 5) { bad.arg_cnt_in = 0; }
        if (test == 6) { bad.arg_cnt_out = 2; }
        if (test == 7) { bad.ioctlv_vecs.clear(); }
        if (test == 8) { bad.ioctlv_vecs.pop_back(); }
        if (test == 9) { bad.ioctlv_vecs[0].addr = 0x53ff40; }
        if (test == 10) { bad.ioctlv_vecs[0].len = 676; }
        if (test == 11) { bad.ioctlv_vecs[1].addr += 32; }
        if (test == 12) { bad.ioctlv_vecs[1].len = 215; }
        if (test == 13) { bad.ioctlv_vecs[1].len = 217; }
        if (test == 14) { bad.ioctlv_vecs.push_back({0, 0}); }
        if (test == 15) { bad.ioctl_cmd = 0x1d; }
        try { if (kernel.ioctlv(context, bad) != IPC_OK) { ++refused; } }
        catch (const std::runtime_error&) { ++refused; }
        for (unsigned i = 0; i < 280; ++i) { if (guarded[i] != 0xa5) { return 15; } }
        if (devices::experiment_stm_pending() != pending || pending->cmd != original.cmd || pending->fd != original.fd ||
            pending->req_addr != original.req_addr || pending->ioctl_cmd != original.ioctl_cmd ||
            pending->in_buf != original.in_buf || pending->out_buf != original.out_buf) { return 16; }
    }
    if (refused != 16) { return 18; }
    std::cout << "ES_DI_TICKET_SHARED_KERNEL_FD4_OUTPUT216_GUARDS64_REFUSALS16_PENDING_PASS\n";
    return 0;
}
'''
host = output / 'device-probe.cpp'
host.write_text(text)
sources = [host, output / 'es_device.cpp', output / 'di_device.cpp', output / 'fs_device.cpp', output / 'stm_device.cpp',
    root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hw/mmio_dispatcher.cpp']
exe = output / 'device-probe'
compiled = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(output), '-I', str(runtime / 'include'),
    *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'
ticket_path = Path('work/private-game/disc/DATA/ticket.bin')
env['SHSM_ES_TICKET_PATH'] = str(ticket_path)
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
(output / 'execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
line = next(line for line in result.stdout.splitlines() if line.startswith('ES_DI_TICKET_BYTES '))
actual = bytes(map(int, line.split()[1:]))
oracle_path = root / 'dolphin-es-di-ticket-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
assert actual == base64.b64decode(oracle['ticketViewPhysical'])
legacy_env = dict(env)
del legacy_env['SHSM_ES_TICKET_PATH']
legacy = subprocess.run([str(exe), 'legacy'], env=legacy_env, capture_output=True, text=True, timeout=30)
assert legacy.returncode == 0 and not legacy.stderr and 'LEGACY_ES_TITLE_FD3_OUTPUT8_GUARDS24_PASS' in legacy.stdout
cases = {'missing': None, 'empty': '', 'unreadable': str(output / 'absent-ticket.bin'), 'directory': str(output)}
ticket = ticket_path.read_bytes()
for label, data in [('short', ticket[:-1]), ('long', ticket + b'\0'), ('huge', ticket + bytes(65536))]:
    path = output / (label + '-ticket.bin')
    path.write_bytes(data)
    cases[label] = str(path)
for label, offset in [('signature', 3), ('version', 0x1bc), ('title', 0x1e3)]:
    data = bytearray(ticket)
    data[offset] ^= 1
    path = output / (label + '-ticket.bin')
    path.write_bytes(data)
    cases[label] = str(path)
for label, path in cases.items():
    negative_env = dict(env)
    if path is None:
        del negative_env['SHSM_ES_TICKET_PATH']
    else:
        negative_env['SHSM_ES_TICKET_PATH'] = path
    negative = subprocess.run([str(exe), 'negative'], env=negative_env, capture_output=True, text=True, timeout=30)
    assert negative.returncode == 17 and not negative.stderr, label + ': ' + negative.stdout + negative.stderr
(output / 'device-verification.json').write_text(json.dumps({'result': 'ACTUAL_ES_DI_TICKET_SHARED_KERNEL_OWN_VIEW216_ORIGINAL_MATCH_PASS',
    'verifierSha256': sha(Path(__file__)), 'preparationSha256': sha(output / 'preparation.json'),
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'oracleSha256': sha(oracle_path), 'ticketSha256': sha(ticket_path), 'viewSha256': hashlib.sha256(actual).hexdigest(),
    'requestRefusals': 16, 'metadataRefusals': list(cases), 'limits': [
        'Actual shared kernel allocatesDI3/ES4; strict NULL-input1B service preserves pendingSTM and guard64.',
        'Legacy title FD3 still works without ticket path; malformed source/request changes no output.',
        'Structural identity only, not cryptographic signature verification. No nonnull-ticket/other revision support.',
        'Component test not native PPC flush/submission/IRQ/response lifetime or completed game boot.']}, indent=2) + '\n')
print('PASS actual ES/shared kernel FD4/full216 equals original/guards64/pending/16request refusals/10metadata refusals/legacyFD3 no-ticket')
