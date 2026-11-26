"""Audit exact cold IPC store and fresh live/disabled startup boundaries."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'mass-ipc-startup-boot'
base = root / 'mass-si-resume-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_ipc_startup_boot.py'))
assert build['originalProofSha256'] == sha(root / 'dolphin-ipc-startup/comparison.json')
assert build['backendProofSha256'] == sha(root / 'ipc-control-backend/comparison.json')
prior = json.loads((base / 'build.json').read_text())
for row, old in zip(build['records'], prior['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] != 'output_67.cpp':
        assert row == old
    else:
        before = '    // 0x80241C38: 7C83012E\n    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[3] + ctx.gpr[0], ctx.gpr[4]); // stwx'
        after = before.replace('bat_memory_write32', 'experiment_ipc_startup_store')
        source = Path(row['source']).read_text()
        assert source.count(after) == 1 and source.replace(after, before) == Path(old['source']).read_text()
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert build['entrySha256'] == sha(output / 'mass_boot.cpp')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
assert (output / 'boot-quarantine.tsv').read_bytes() == (base / 'boot-quarantine.tsv').read_bytes()
observed = (root / 'mass-ipc-startup-observer/observed-boot.log').read_text()
assert 'IPC_STARTUP_ACCESS 80241c30 80242140 a032 80241c38 cd000004 38 d000004 1 5 4' in observed
assert 'IPC_STARTUP_BEFORE 0 0 0 0 40000000 0 0 40f8' in observed
fresh = {}
for mode in ('live', 'disabled'):
    environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    if mode == 'disabled':
        environment['SHSM_IPC_STARTUP_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'), str(root / 'sram-native/settings.bin')], env=environment,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    log = result.stdout
    assert 'BOOT_SI_DELIVERY entries=4 callbacks=4' in log
    assert 'BOOT_FINITE_MEM2 steps=1765312 returned=1' in log
    assert 'BOOT_FLUSH entries=3 phase=0 barriers=3' in log
    boundary = next(line for line in log.splitlines() if line.startswith('BOOT_BOUNDARY '))
    if mode == 'live':
        assert 'BOOT_IPC_STARTUP writes=1 control=38' in log
        assert re.fullmatch(r'BOOT_BOUNDARY pc=80212ff4 lr=8024262c msr=a032 calls=\d+ reason=Flush syscall CPU/site/profile unverified', boundary)
    else:
        assert 'BOOT_IPC_STARTUP writes=0 control=0' in log
        assert re.fullmatch(r'BOOT_BOUNDARY pc=80241c30 lr=80242140 msr=a032 calls=\d+ reason=Cold IPC client control write profile unverified', boundary)
    fresh[mode] = boundary
native = root / 'ipc-startup-native/comparison.json'
assert json.loads(native.read_text())['inputBuildSha256'] == sha(output / 'build.json')
(output / 'audit.json').write_text(json.dumps({'result': 'COLD_IPC_ORIGINAL_STORE_RETURNS_NEXT_EE_FLUSH_GUARD_RETAINED',
    'buildSha256': sha(output / 'build.json'), 'auditorSha256': sha(Path(__file__)), 'nativeProofSha256': sha(native),
    'freshBoundaries': fresh,
    'limits': ['Only measured cold control store accepted through existing IPC storage/projection.',
        'No request production, IPC IRQ delivery, client-init completion or firstframe/menu/audio proof.',
        'Next cache syscall withEEA032needs separate original comparison; do not force interrupts off.']}, indent=2) + '\n')
print('PASS fresh cold IPC store/control38/counter1; disabled unchanged; next EE flush refusal retained')
