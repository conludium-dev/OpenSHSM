"""Fresh enabled/disabled replay of the exact narrow EXISync profile."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

output = Path('work/private-game/static-recomp/mass-exi-sync-ee-boot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', 'experiments/wii-static-recomp/verify_uart_ee_dolphin.py'], check=True)
ghidra_root = Path('work/private-game/static-recomp/exi-sync-ee/ghidra')
ghidra = json.loads((ghidra_root / 'verification.json').read_text())
assert ghidra['runnerSha256'] == sha(Path('experiments/wii-static-recomp/verify_exi_sync_ghidra.py'))
assert ghidra['records'][0]['instructions'] == 159 and ghidra['records'][0]['discoveredBodyBytes'] == 636
assert ghidra['records'][0]['assemblySha256'] == sha(ghidra_root / 'EXISync.asm')
assert ghidra['records'][0]['decompiledSha256'] == sha(ghidra_root / 'EXISync.c')
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_exi_sync_ee_boot.py'))
assert build['observerParentSha256'] == sha(Path('experiments/wii-static-recomp/observe_exi_sync_boot.py'))
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
base = json.loads(Path('work/private-game/static-recomp/mass-stm-async-boot/build.json').read_text())
assert len(build['records']) == 125
assert [row['file'] for row, old in zip(build['records'], base['records']) if row != old] == ['output_62.cpp']
assert next(row for row in build['records'] if row['file'] == 'output_62.cpp')['sourceSha256'] == next(row for row in base['records'] if row['file'] == 'output_62.cpp')['sourceSha256']
exe = output / 'openshsm-exi-sync-observer'
assert sha(exe) == build['executableSha256']
environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
results = {}
for mode in ('live', 'disabled'):
    env = dict(environment)
    if mode == 'disabled':
        env['SHSM_EXI_SYNC_EE_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        'work/private-game/static-recomp/sram-native/settings.bin'], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7 and not result.stderr
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in result.stdout
    log = output / (mode + '-boot.log')
    log.write_text(result.stdout)
    reads = [line for line in result.stdout.splitlines() if line.startswith('EXI_SYNC_EE_READ')]
    if mode == 'live':
        assert reads[:4] == ['EXI_SYNC_EE_READ lr=80240444 control=34', 'EXI_SYNC_EE_READ lr=80240464 control=30',
            'EXI_SYNC_EE_READ lr=802404d0 control=34', 'EXI_SYNC_EE_READ lr=80240500 control=34']
        assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in result.stdout
        assert 'reason=STM sender caller/value unverified' in result.stdout
        assert 'BOOT_STM_NEXT_PACKET 324927616 0 0 0 1' in result.stdout
        for view in ('PHYSICAL', 'CACHED'):
            assert 'BOOT_NEXT_OPEN_PATH_' + view + ' 47 100 101 118 47 102 115 0' in result.stdout
    else:
        assert not reads and 'BOOT_BOUNDARY pc=8020def4 lr=80240444 msr=a032' in result.stdout
    boundary = next(line for line in result.stdout.splitlines() if line.startswith('BOOT_BOUNDARY'))
    results[mode] = {'boundary': boundary, 'reads': len(reads), 'logSha256': sha(log)}
    print(mode + ': ' + boundary)
(output / 'audit.json').write_text(json.dumps({'result': 'NARROW_EXISYNC_EE_BOOT_ADVANCE_DISABLED_CONTROL_PASS',
    'verifierSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'), 'results': results,
    'originalProofSha256': sha(Path('work/private-game/static-recomp/dolphin-uart-ee/comparison.json')),
    'ghidraProofSha256': sha(Path('work/private-game/static-recomp/exi-sync-ee/ghidra/verification.json')),
    'limits': ['Original EE UART endpoints, native guarded whole boot; not cycle-accurate or full retail/gameplay equivalence.',
        'Next guarded OPEN path /dev/fs independently read in both MEM2 cache projections; no FS response supplied.']}, indent=2) + '\n')
