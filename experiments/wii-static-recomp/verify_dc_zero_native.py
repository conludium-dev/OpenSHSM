"""Compare whole compiled zero/flush cases with original cache visibility."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'dc-zero-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_dc_zero_dolphin.py')], check=True)
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_dc_zero_native.py')
assert build['parentSha256'] == sha(experiment / 'build_reset_code_native.py')
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(name)) == digest
base = json.loads((private / 'mass-reset-code-boot/boot.json').read_text())
old = Path(next(row['source'] for row in base['records'] if row['file'] == 'output_63.cpp')).read_text()
new = Path(next(row['source'] for row in build['records'] if row['file'] == 'output_63.cpp')).read_text()
assert old.count(build['before']) == 1 and new == old.replace(build['before'], build['after'])
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
section = next(i for i in range(7) if layout[18 + i] <= 0x8021307c < layout[18 + i] + layout[36 + i])
assert struct.unpack_from('>I', dol, layout[section] + 0x8021307c - layout[18 + section])[0] == 0x7c001fec
ghidra_path = private / 'dolphin-dc-zero/ghidra'
ghidra = json.loads((ghidra_path / 'verification.json').read_text())
assert ghidra['result'] == 'DC_ZERO_GHIDRA_FULL11_44_PASS'
record = ghidra['records'][0]
assert record['assemblySha256'] == sha(ghidra_path / 'DCZeroRange.asm') and record['decompiledSha256'] == sha(ghidra_path / 'DCZeroRange.c')
oracle = json.loads((private / 'dolphin-dc-zero/comparison.json').read_text())
def validate(text):
    lines = text.splitlines()
    assert len(lines) == 128
    for index, state in enumerate(oracle['states']):
        scalar = list(state['scalar'])
        scalar[9] = 0x807f0000
        expected = [('DCZERO_CASE', [index, *scalar, state['lines']]),
            ('DCZERO_MEMORY', [index, 0x80550000, *struct.unpack('>40I', bytes.fromhex(state['cachedHex']))]),
            ('DCZERO_MEMORY', [index, 0xc0550000, *struct.unpack('>40I', bytes.fromhex(state['beforeRawHex']))]),
            ('DCZERO_FLUSHED', [index, *struct.unpack('>40I', bytes.fromhex(state['afterRawHex']))])]
        for line, (tag, values) in zip(lines[index * 4:index * 4 + 4], expected):
            assert line.split()[0] == tag and list(map(int, line.split()[1:])) == values, (index, tag)
exe = output / 'dc-zero-probe'
assert build['executableSha256'] == sha(exe)
for mode in ('normal', 'guards'):
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', *([] if mode == 'normal' else [mode])], capture_output=True, text=True, timeout=30)
    assert result.returncode == build['results'][mode]['returnCode'] == 0 and not result.stderr
    assert build['results'][mode]['logSha256'] == sha(output / (mode + '.log'))
    assert result.stdout == (output / (mode + '.log')).read_text()
    if mode == 'normal':
        validate(result.stdout)
    else:
        assert result.stdout == 'DCZERO_GUARDS 8 ZERO_DISABLED_RETURN\n'
for row_index in (1, 2, 3):
    lines = (output / 'normal.log').read_text().splitlines()
    tokens = lines[row_index].split()
    tokens[-1] = str(int(tokens[-1]) ^ 1)
    lines[row_index] = ' '.join(tokens)
    try:
        validate('\n'.join(lines))
    except AssertionError:
        pass
    else:
        raise AssertionError('Mutated cached/raw/post-flush accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'COMPILED_DC_ZERO32_CACHE_RAW_FLUSH_ABI8_GUARDS_PASS',
    'buildSha256': sha(output / 'build.json'), 'verifierSha256': sha(Path(__file__)),
    'oracleSha256': sha(private / 'dolphin-dc-zero/comparison.json'), 'ghidraSha256': sha(ghidra_path / 'verification.json'),
    'limits': ['Existing cache storage/replacement/dirty writeback reused; cached WIMG0/HID0C200/MSR2032 only.',
        'Allocation uses existing RAM line fill before zeroing; no cycle-exact bus access/replacement timing proof.',
        'Native copied syscall-vector fixture for original flush, not a retail loader; full-game/uncached/dcbz_l unverified.']}, indent=2) + '\n')
print('PASS32compiled DCZeroRange populated/missing cached/raw/flush/ABI,8guards and disabled zero-length return')
