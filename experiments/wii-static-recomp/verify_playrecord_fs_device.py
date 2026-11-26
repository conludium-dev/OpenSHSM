"""Exercise real shared-kernel FD reuse and measured transfers without PPC claims."""
from pathlib import Path
import base64
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'playrecord-fs-device'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
prep = json.loads((output / 'preparation.json').read_text())
assert prep['preparerSha256'] == sha(experiment / 'prepare_playrecord_fs_device.py')
for path, digest in {**prep['sourceHashes'], **prep['headerHashes']}.items():
    assert sha(Path(path)) == digest
lab = output / 'pc-owned-playrecord.bin'
seed_hash = sha(lab)
assert seed_hash == prep['pcOwnedSeedSha256']
capture_path = root / 'dolphin-playrecord-events-disc/fpr-init-true-dolphin.json'
assert sha(capture_path) == prep['oracleCaptureSha256']
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
seed = base64.b64decode(capture['playrecordLabFile'])
for name, content in [('short',seed[:-1]), ('long',seed + b'\0')]:
    (output / ('invalid-' + name + '.bin')).write_bytes(content)
text = (experiment / 'fs_pending_device_probe.cpp').read_text().split('    for (unsigned index = 3;',1)[0]
text = '#include <algorithm>\n#include <array>\n#include <cstdlib>\n' + text
text = text.replace('int main() {', 'int main(int argc, char** argv) {\n    if (argc != 2) { return 1; }')
text += r'''    if (kernel.open(context, "/dev/fs", 0) != 2) { return 5; }
    kernel.register_device(devices::create_di_device());
    kernel.register_device(devices::create_es_device());
    if (kernel.open(context, "/dev/di", 0) != 3 || kernel.open(context, "/dev/es", 0) != 4 ||
        kernel.close(context, 4) != IPC_OK) { return 6; }
    auto* guarded = context.mmu.get_ptr(0x493100);
    std::fill(guarded, guarded + 192, 0xa5);
    const auto original = *pending;
    unsigned refused = 0;
    auto retained = [&]() {
        return devices::experiment_stm_pending() == pending && pending->cmd == original.cmd &&
            pending->fd == original.fd && pending->req_addr == original.req_addr &&
            pending->in_buf == original.in_buf && pending->out_buf == original.out_buf &&
            std::all_of(guarded, guarded + 192, [](uint8_t v) { return v == 0xa5; });
    };
    const char* path = "/title/00000001/00000002/data/play_rec.dat";
    for (unsigned test = 0; test < 9; ++test) {
        unsetenv("SHSM_PLAYRECORD_LAB_FILE");
        if (test == 1) { setenv("SHSM_PLAYRECORD_LAB_FILE", "", 1); }
        if (test == 2) { setenv("SHSM_PLAYRECORD_LAB_FILE", "work/private-game/static-recomp/playrecord-fs-device/missing.bin", 1); }
        if (test == 3) { setenv("SHSM_PLAYRECORD_LAB_FILE", "work/private-game/static-recomp/playrecord-fs-device/invalid-short.bin", 1); }
        if (test == 4) { setenv("SHSM_PLAYRECORD_LAB_FILE", "work/private-game/static-recomp/playrecord-fs-device/invalid-long.bin", 1); }
        if (test >= 5) { setenv("SHSM_PLAYRECORD_LAB_FILE", argv[1], 1); }
        try {
            kernel.open(context, test == 8 ? "/title/00000001/00000002/data/unknown.dat" : path,
                test == 5 ? 0 : test == 6 ? 1 : test == 7 ? 2 : 3);
        } catch (const std::runtime_error&) { ++refused; }
        if (!retained()) { return 7; }
    }
    if (refused != 9) { return 8; }
    setenv("SHSM_PLAYRECORD_LAB_FILE", argv[1], 1);
    if (kernel.open(context, path, 3) != 4) { return 9; }
    for (unsigned test = 0; test < 7; ++test) {
        try {
            if (test == 0) { kernel.open(context, path, 3); }
            if (test == 1) { kernel.read(context, 4, 0x493100, 128); }
            if (test == 2) { kernel.read(context, 4, 0x493120, 127); }
            if (test == 3) { kernel.read(context, 4, 0x493120, 129); }
            if (test == 4) { kernel.seek(context, 4, 0, 0); }
            if (test == 5) { kernel.write(context, 4, 0x493120, 128); }
            if (test == 6) { kernel.close(context, 4); }
        } catch (const std::runtime_error&) { ++refused; }
        if (!retained()) { return 10; }
    }
    if (refused != 16 || kernel.read(context, 99, 0x493120, 128) != IPC_EINVAL ||
        kernel.seek(context, 99, 0, 0) != IPC_EINVAL) { return 11; }
    if (kernel.read(context, 4, 0x493120, 128) != 128) { return 12; }
    std::cout << "PLAYRECORD_READ";
    for (unsigned i = 0; i < 128; ++i) { std::cout << ' ' << unsigned(guarded[32 + i]); }
    std::cout << '\n';
    std::array<uint8_t,192> saved{};
    std::copy_n(guarded,192,saved.begin());
    for (unsigned test = 0; test < 5; ++test) {
        try {
            if (test == 0) { kernel.read(context, 4, 0x493120, 128); }
            if (test == 1) { kernel.seek(context, 4, 1, 0); }
            if (test == 2) { kernel.seek(context, 4, 0, 1); }
            if (test == 3) { kernel.seek(context, 4, -1, 0); }
            if (test == 4) { kernel.write(context, 4, 0x493120, 128); }
        } catch (const std::runtime_error&) { ++refused; }
        if (!std::equal(saved.begin(),saved.end(),guarded)) { return 13; }
    }
    if (refused != 21 || kernel.seek(context, 4, 0, 0) != 0 ||
        devices::experiment_stm_pending() != pending || !std::equal(saved.begin(),saved.end(),guarded)) { return 14; }
    for (unsigned i = 0; i < 192; ++i) {
        if ((i < 32 || i >= 160) && guarded[i] != 0xa5) { return 15; }
    }
    std::cout << "PLAYRECORD_SHARED_KERNEL_FD4_OPEN3_READ128_SEEK0_21REFUSALS_GUARDS64_PENDING_PASS\n";
    return 0;
}
'''
host = output / 'device-probe.cpp'
host.write_text(text)
sources = [host, *[output / name for name in ('fs_device.cpp','stm_device.cpp','di_device.cpp','es_device.cpp')],
    root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hw/mmio_dispatcher.cpp']
exe = output / 'device-probe'
result = subprocess.run(['arch','-arm64','clang++','-std=c++20','-O0','-I',str(output),'-I',str(runtime / 'include'),
    *map(str,sources),'-o',str(exe)],capture_output=True,text=True,timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
env = {key:value for key,value in os.environ.items() if not key.startswith('SHSM_')}
env['SHSM_ES_TMD_PATH'] = 'work/private-game/disc/DATA/tmd.bin'
result = subprocess.run([str(exe),str(lab)],env=env,capture_output=True,text=True,timeout=30)
(output / 'execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
payload = bytes(map(int,next(line for line in result.stdout.splitlines() if line.startswith('PLAYRECORD_READ ')).split()[1:]))
assert payload == seed == base64.b64decode(capture['playrecordBufferPhysical'])
assert sha(lab) == seed_hash
(output / 'verification.json').write_text(json.dumps({'result':'SAME_FS_KERNEL_FD4_OPEN3_READ128_SEEK0_LAB_BYTE_MATCH_PASS',
    'verifierSha256':sha(Path(__file__)), 'preparationSha256':sha(output / 'preparation.json'),
    'sourceHashes':{str(path):sha(path) for path in sources}, 'executableSha256':sha(exe),
    'oracleSha256':sha(capture_path), 'pcOwnedSeedSha256':seed_hash, 'refusals':21,
    'limits':['Real shared kernel reuses FD4 after ES close; READ128 matches original LAB, guards64/pendingSTM unchanged.',
        'Same FS class/read-only stream; WRITE/CLOSE not admitted and seed unchanged.',
        'Component only: original PPC sender/IRQ/callback/lifetime and first screen not yet verified.']},indent=2) + '\n')
print('PASS SAME FS/kernel FD4 OPEN3/READ128/SEEK0/originalLAB128match/guards64/pendingSTM/21 refusals/PC-owned seed unchanged')
