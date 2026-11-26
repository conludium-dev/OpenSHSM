"""Original MEM2-line comparison and old MEM1/EE-off same-object regressions."""
from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'flush-packet-profile'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['returnCode'] == 0
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_flush_packet_native.py'))
assert build['baseBuildSha256'] == sha(root / 'mass-ipc-startup-boot/build.json')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
prior = json.loads((root / 'mass-ipc-startup-boot/build.json').read_text())
assert len(build['records']) == len(prior['records']) == 125
for row, old in zip(build['records'], prior['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] == old['sourceSha256']
    assert sha(Path(row['object'])) == row['objectSha256']
    if row['file'] not in ('output_63.cpp', 'output_64.cpp'):
        assert row == old
profile = json.loads((output / 'packet-profile.json').read_text())
assert profile['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_flush_packet_profile.py'))
assert profile['headerSha256'] == sha(output / 'flush_syscall.h')
assert profile['parentSha256'] == sha(Path('experiments/wii-static-recomp/build_flush_ee_profile.py'))
assert profile['dolSha256'] == sha(Path('work/private-game/disc/DATA/sys/main.dol'))
assert profile['ghidraSha256'] == sha(root / 'dolphin-flush-syscall/ghidra/verification.json')
assert profile['observationSha256'] == sha(root / 'mass-flush-packet-observer/observation.json')
exe = output / 'flush-ee-probe'
assert sha(exe) == build['executableSha256']
proofs = {}
modes = [('packet', 'dolphin-flush-packet', {}, 0x80242240),
    ('old-caller-mem2', 'dolphin-flush-packet', {'SHSM_FLUSH_OLD_CALLER': '1'}, 0x8024262c),
    ('old-mem1', 'dolphin-flush-ee', {'SHSM_FLUSH_OLD_CALLER': '1', 'SHSM_FLUSH_MEM1': '1'}, 0x8024262c),
    ('ee-off-mem1', 'dolphin-flush-syscall', {'SHSM_FLUSH_OLD_CALLER': '1', 'SHSM_FLUSH_MEM1': '1', 'SHSM_FLUSH_EE_OFF': '1'}, 0x8024262c)]
for mode, directory, options, caller in modes:
    oracle_path = root / directory / 'comparison.json'
    oracle = json.loads(oracle_path.read_text())
    capture = json.loads((root / directory / 'fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
    data = base64.b64decode(capture['data'])
    environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    environment.update(options)
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], env=environment,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and not result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 32
    for index in range(16):
        nonzero = int(index % 8 != 0)
        expected = oracle['states'][index][:12] + [caller, nonzero, nonzero]
        assert lines[index * 2] == 'FLUSH_CASE ' + ' '.join(map(str, [index] + expected))
        memory = struct.unpack_from('>40I', data, index * 736 + 128)
        assert lines[index * 2 + 1] == 'FLUSH_MEMORY ' + ' '.join(map(str, [index, *memory]))
    proofs[mode] = sha(oracle_path)
guards = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'],
    capture_output=True, text=True, timeout=30)
assert guards.returncode == 0 and guards.stdout == 'FLUSH_GUARDS 17\n' and not guards.stderr
(output / 'comparison.json').write_text(json.dumps({'result': 'MEM2_PACKET16_OLD_MEM2_16_MEM1_EE16_OFF16_MATCH_17_GUARDS',
    'buildSha256': sha(output / 'build.json'), 'verifierSha256': sha(Path(__file__)), 'originalProofs': proofs,
    'profileSha256': sha(output / 'packet-profile.json'), 'guards': 17,
    'limits': ['Caller addresses replace original laboratory return sites; LR-independent algorithm is source inference.',
        'No full original IPC packet submission, concurrent IRQ or physical timing proof.']}, indent=2) + '\n')
print('PASS64 current original comparisons (MEM2/new-old callers, MEM1/EE-on-off);17guards')
