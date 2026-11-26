"""Verify whole compiled reset-code branches against the unpatched original fixture."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'reset-code-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_reset_code_dolphin.py')], check=True)
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_reset_code_native.py')
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
base = json.loads((private / 'mass-uart-ri-boot/boot.json').read_text())
old = Path(next(row['source'] for row in base['records'] if row['file'] == 'output_63.cpp')).read_text()
new = Path(next(row['source'] for row in build['records'] if row['file'] == 'output_63.cpp')).read_text()
assert old.count(build['before']) == 1 and new == old.replace(build['before'], build['after'])
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
section = next(i for i in range(7) if layout[18 + i] <= 0x80219504 < layout[18 + i] + layout[36 + i])
assert struct.unpack_from('>I', dol, layout[section] + 0x80219504 - layout[18 + section])[0] == 0x80033024
ghidra_path = private / 'dolphin-reset-code/ghidra'
ghidra = json.loads((ghidra_path / 'verification.json').read_text())
assert ghidra['result'] == 'RESET_CODE_GHIDRA_FULL12_48_PASS'
row = ghidra['records'][0]
assert row['assemblySha256'] == sha(ghidra_path / 'OSGetResetCode.asm') and row['decompiledSha256'] == sha(ghidra_path / 'OSGetResetCode.c')
oracle = json.loads((private / 'dolphin-reset-code/comparison.json').read_text())
expected = []
for index, state in enumerate(oracle['states']):
    state = list(state)
    state[8] = 0x807f0000
    expected.append([index, *state, 1 if index % 2 == 0 else 0])
exe = output / 'reset-code-probe'
assert sha(exe) == build['executableSha256']
for mode in ('normal', 'guards'):
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', *([] if mode == 'normal' else [mode])], capture_output=True, text=True, timeout=30)
    assert result.returncode == build['results'][mode]['returnCode'] == 0 and not result.stderr
    assert build['results'][mode]['logSha256'] == sha(output / (mode + '.log'))
    assert result.stdout == (output / (mode + '.log')).read_text()
    if mode == 'normal':
        actual = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('RESET_CASE ')]
        assert actual == expected
    else:
        assert result.stdout == 'RESET_GUARDS 7 WARM_DISABLED_RETURN\n'
(output / 'comparison.json').write_text(json.dumps({'result': 'COMPILED_RESET_CODE16_BRANCHES_ABI7_GUARDS_PASS',
    'buildSha256': sha(output / 'build.json'), 'verifierSha256': sha(Path(__file__)),
    'oracleSha256': sha(private / 'dolphin-reset-code/comparison.json'), 'ghidraSha256': sha(ghidra_path / 'verification.json'),
    'limits': ['Existing vendor PI zero read agrees with measured emulator cold profile; no general reset-state emulation.',
        'Negative non-cold register uses isolated cleared dispatcher/readback8 fixture, not game hardware evidence.',
        'Native caller sentinel replaces original lab return; physical reset events/buttons/persistence unverified.']}, indent=2) + '\n')
print('PASS16compiled reset-code calls/7guards; disabled profile still executes original warm branch without PI reads')
