"""Exercise the actual ES/shared kernel with exact ES16 and atomic refusals."""
from pathlib import Path
import base64
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'es-consumption-device'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
prep = json.loads((output / 'preparation.json').read_text())
assert prep['preparerSha256'] == sha(experiment / 'prepare_es_consumption_device.py')
assert prep['adapterSha256'] == sha(experiment / 'es_consumption_adapter.h')
for path, digest in {**prep['sourceHashes'], **prep['headerHashes']}.items():
    assert sha(Path(path)) == digest
text = (experiment / 'fs_pending_device_probe.cpp').read_text().split('    for (unsigned index = 3;', 1)[0]
text = ('#include "es_consumption_adapter.h"\n' + text).replace('int main() {', 'int main(int argc, char** argv) {')
text += r'''    if (kernel.open(context, "/dev/fs", 0) != 2) { return 5; }
    kernel.register_device(devices::create_di_device());
    kernel.register_device(devices::create_es_device());
    if (kernel.open(context, "/dev/di", 0) != 3 || kernel.open(context, "/dev/es", 0) != 4) { return 6; }
    auto* input = context.mmu.get_ptr(0x53fca0);
    auto* guarded = context.mmu.get_ptr(0x53fcb0);
    const auto title = experiment_load_es_title(std::getenv("SHSM_ES_TMD_PATH"));
    const auto view = experiment_load_es_ticket_view("work/private-game/disc/DATA/ticket.bin", title);
    std::copy_n(view.begin() + 4, 8, input);
    std::fill(guarded, guarded + 36, 0xa5);
    IpcRequest req{};
    req.cmd = 7; req.fd = 4; req.req_addr = 0x135e0080; req.ioctl_cmd = 0x16;
    req.arg_cnt_in = 1; req.arg_cnt_out = 2;
    req.ioctlv_vecs = {{0x53fca0, 8}, {0, 0}, {0x53fcc0, 4}};
    if (argc > 1) {
        try { kernel.ioctlv(context, req); return 7; } catch (const std::runtime_error&) {}
        for (unsigned i = 0; i < 36; ++i) { if (guarded[i] != 0xa5) { return 8; } }
        if (devices::experiment_stm_pending() != pending) { return 9; }
        std::cout << "ES16_SOURCE_OR_POLICY_REFUSAL_ATOMIC\n";
        return 17;
    }
    if (kernel.ioctlv(context, req) != IPC_OK) { return 10; }
    std::cout << "ES16_COUNT";
    for (unsigned i = 0; i < 4; ++i) { std::cout << ' ' << unsigned(guarded[16 + i]); }
    std::cout << '\n';
    for (unsigned i = 0; i < 36; ++i) { if ((i < 16 || i >= 20) && guarded[i] != 0xa5) { return 11; } }
    for (unsigned i = 0; i < 8; ++i) { if (input[i] != view[4 + i]) { return 12; } }
    const auto original = *pending;
    unsigned refused = 0;
    for (unsigned test = 0; test < 18; ++test) {
        auto bad = req;
        std::fill(guarded, guarded + 36, 0xa5);
        if (test == 0) { bad.cmd = 6; }
        if (test == 1) { bad.fd = 99; }
        if (test == 2) { bad.fd = 3; }
        if (test == 3) { bad.req_addr += 32; }
        if (test == 4) { bad.ioctl_cmd = 0x1d; }
        if (test == 5) { bad.arg_cnt_in = 0; }
        if (test == 6) { bad.arg_cnt_out = 1; }
        if (test == 7) { bad.ioctlv_vecs.clear(); }
        if (test == 8) { bad.ioctlv_vecs.pop_back(); }
        if (test == 9) { bad.ioctlv_vecs[0].addr += 32; }
        if (test == 10) { bad.ioctlv_vecs[0].len = 7; }
        if (test == 11) { bad.ioctlv_vecs[1].addr = 0x53fc80; }
        if (test == 12) { bad.ioctlv_vecs[1].len = 8; }
        if (test == 13) { bad.ioctlv_vecs[2].addr += 32; }
        if (test == 14) { bad.ioctlv_vecs[2].len = 3; }
        if (test == 15) { bad.ioctlv_vecs[2].len = 5; }
        if (test == 16) { bad.ioctlv_vecs.push_back({0, 0}); }
        if (test == 17) { input[0] ^= 1; }
        try { if (kernel.ioctlv(context, bad) != IPC_OK) { ++refused; } }
        catch (const std::runtime_error&) { ++refused; }
        if (test == 17) { input[0] ^= 1; }
        for (unsigned i = 0; i < 36; ++i) { if (guarded[i] != 0xa5) { return 13; } }
        if (devices::experiment_stm_pending() != pending || pending->cmd != original.cmd ||
            pending->fd != original.fd || pending->req_addr != original.req_addr ||
            pending->in_buf != original.in_buf || pending->out_buf != original.out_buf) { return 14; }
    }
    if (refused != 18) { return 15; }
    std::cout << "ES16_KERNEL_FD4_GUARDS32_PENDING_18REFUSALS_PASS\n";
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
env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin', SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',
    SHSM_ES_LAB_CONSUMPTION='1')
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
(output / 'execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
actual = bytes(map(int, next(line for line in result.stdout.splitlines() if line.startswith('ES16_COUNT ')).split()[1:]))
oracle_path = root / 'dolphin-es-consumption-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
assert actual == base64.b64decode(oracle['consumptionCountPhysical'])[:4]
cases = {}
for key, values in [('SHSM_ES_LAB_CONSUMPTION', [None, '', '0', 'true', '2']),
    ('SHSM_ES_TICKET_PATH', [None, '', str(output / 'missing-ticket.bin'), str(output)])]:
    for value in values:
        negative_env = dict(env)
        if value is None:
            del negative_env[key]
        else:
            negative_env[key] = value
        case = key + ':' + str(value)
        negative = subprocess.run([str(exe), 'negative'], env=negative_env, capture_output=True, text=True, timeout=30)
        assert negative.returncode == 17 and not negative.stderr, case + negative.stdout + negative.stderr
        cases[case] = negative.returncode
(output / 'device-verification.json').write_text(json.dumps({'result': 'ACTUAL_ES16_SHARED_KERNEL_COUNT4_ORIGINAL_LAB_MATCH_PASS',
    'verifierSha256': sha(Path(__file__)), 'preparationSha256': sha(output / 'preparation.json'),
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'oracleSha256': sha(oracle_path), 'requestRefusals': 18, 'sourcePolicyRefusals': cases,
    'limits': ['Actual kernel DI3/ES4, count4 and guard32/pendingSTM preserved; malformed requests refuse atomically.',
        'Explicit LAB policy required; own-ticket structural identity, not cryptographic or physical IOS proof.',
        'Component only, not original PPC sender/IRQ/return/lifetime or first screen.']}, indent=2) + '\n')
print('PASS actual ES16/kernel FD4/count4 originalLABmatch/guards32/pendingSTM/18request-9policy-source refusals')
