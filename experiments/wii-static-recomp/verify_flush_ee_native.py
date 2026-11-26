"""Compare current compiled EE flush and retained EE-off path to original captures."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'flush-ee-profile'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['returnCode'] == 0
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_flush_ee_native.py'))
assert build['baseBuildSha256'] == sha(root / 'mass-ipc-startup-boot/build.json')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
prior = json.loads((root / 'mass-ipc-startup-boot/build.json').read_text())
assert len(build['records']) == len(prior['records']) == 125
for row, old in zip(build['records'], prior['records']):
    assert sha(Path(row['source'])) == row['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
    assert row['sourceSha256'] == old['sourceSha256']
    if row['file'] not in ('output_63.cpp', 'output_64.cpp'):
        assert row == old
exe = output / 'flush-ee-probe'
assert sha(exe) == build['executableSha256']
proofs = {}
for mode, directory in (('ee', 'dolphin-flush-ee'), ('off', 'dolphin-flush-syscall')):
    oracle_path = root / directory / 'comparison.json'
    oracle = json.loads(oracle_path.read_text())
    capture = json.loads((root / directory / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
    data = base64.b64decode(capture['data'])
    environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    if mode == 'off':
        environment['SHSM_FLUSH_EE_OFF'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], env=environment,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and not result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 32
    for index in range(16):
        nonzero = int(index % 8 != 0)
        expected = oracle['states'][index][:12] + [0x8024262c, nonzero, nonzero]
        assert lines[index * 2] == 'FLUSH_CASE ' + ' '.join(map(str, [index] + expected))
        memory = struct.unpack_from('>40I', data, index * 736 + 128)
        assert lines[index * 2 + 1] == 'FLUSH_MEMORY ' + ' '.join(map(str, [index, *memory]))
    proofs[mode] = sha(oracle_path)
guards = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'],
    capture_output=True, text=True, timeout=30)
assert guards.returncode == 0 and guards.stdout == 'FLUSH_GUARDS 16\n' and not guards.stderr
(output / 'comparison.json').write_text(json.dumps({'result': 'CURRENT_DCFLUSH_EE16_EEOFF16_ORIGINAL_MATCH_16_GUARDS',
    'buildSha256': sha(output / 'build.json'), 'verifierSha256': sha(Path(__file__)), 'originalProofs': proofs,
    'guards': 16, 'limits': ['Fixture return address differs from original harness caller.',
        'No pending IRQ concurrency, physical cache timing or original first-screen proof.']}, indent=2) + '\n')
print('PASS current EE16 + EE-off16 original states/physical visibility;16 state-preserving guards')
