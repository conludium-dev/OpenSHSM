"""Compare the whole compiled procedure, retaining real-mode/rfi and default guards."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'memory-protection-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_memory_protection_dolphin.py')], check=True)
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_memory_protection_native.py') and build['returnCode'] == 0
assert build['originalSha256'] == sha(Path('work/private-game/disc/DATA/sys/main.dol'))
assert len(build['records']) == 125 and len(build['changes']) == 38
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(name)) == digest
assert build['planHeaderSha256'] == sha(output / 'memory-protection-bat-plan.h')
exe = output / 'memory-protection-probe'
assert build['executableSha256'] == sha(exe)
base = json.loads((private / 'mass-audio-init-boot/boot.json').read_text())
original_source = Path(next(row['source'] for row in base['records'] if row['file'] == 'output_63.cpp'))
native_source = Path(next(row['source'] for row in build['records'] if row['file'] == 'output_63.cpp')).read_text()
reconstructed = native_source
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
for change in build['changes']:
    assert reconstructed.count(change['after']) == 1
    reconstructed = reconstructed.replace(change['after'], change['before'], 1)
    site = change['site']
    section = next(i for i in range(7) if layout[18 + i] <= site < layout[18 + i] + layout[36 + i])
    opcode = struct.unpack_from('>I', dol, layout[section] + site - layout[18 + section])[0]
    assert f'    // 0x{site:08X}: {opcode:08X}\n' + change['after'] in native_source
assert reconstructed == original_source.read_text()
oracle = json.loads((private / 'dolphin-memory-protection/comparison.json').read_text())
ghidra_dir = private / 'dolphin-memory-protection/ghidra'
ghidra = json.loads((ghidra_dir / 'verification.json').read_text())
assert ghidra['result'] == 'MEMORY_PROTECTION_SELECTED_REAL_MODE_BAT_GHIDRA214_856_PASS'
for row in ghidra['records']:
    assert row['assemblySha256'] == sha(ghidra_dir / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(ghidra_dir / (row['name'] + '.c'))
def validate(text):
    lines = text.splitlines()
    assert len(lines) == 64
    for index, state in enumerate(oracle['states']):
        tags = ['MI_BEFORE', 'MI_CASE', 'MI_AFTER', 'MI_COUNTS']
        actual = []
        for line, tag in zip(lines[index * 4:index * 4 + 4], tags):
            tokens = line.split()
            assert tokens[:2] == [tag, str(index)]
            actual.append(list(map(int, tokens[2:])))
        expected = list(state['scalar'])
        expected[7] = 0x807f0000
        assert actual == [state['beforeBats'], expected, state['afterBats'], [3, 3, 2]], index
validate((output / 'native.log').read_text())
fresh = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
assert fresh.returncode == 0 and not fresh.stderr
validate(fresh.stdout)
guards = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'], capture_output=True, text=True, timeout=30)
assert guards.returncode == 0 and guards.stdout == 'MI_GUARDS 26\n' and not guards.stderr
assert (output / 'guards.log').read_text() == guards.stdout
invalid = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'unsupported'], capture_output=True, text=True, timeout=30)
assert invalid.returncode == 2
for number, token in [(1, 11), (2, 2), (0, 2)]:
    lines = fresh.stdout.splitlines()
    values = lines[number].split()
    values[token] = str(int(values[token]) ^ 1)
    lines[number] = ' '.join(values)
    try:
        validate('\n'.join(lines))
    except AssertionError:
        pass
    else:
        raise AssertionError('Mutated scalar/BAT state accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'WHOLE_COMPILED_MEMORY_PROTECTION16_SCALARS_BAT_TABLE_QUEUE_MATCH',
    'builderProofSha256': sha(output / 'build.json'), 'verifierSha256': sha(Path(__file__)),
    'oracleSha256': sha(private / 'dolphin-memory-protection/comparison.json'),
    'ghidraProofSha256': sha(ghidra_dir / 'verification.json'), 'cases': 16, 'guards': 26,
    'limits': ['Prepared size/mask/table/queue/CPU fixture; same lab caller replaced by native return sentinel.',
        'Existing BAT banks change through32scoped original-instruction writes during MSR2002; physical fetch image and restored code mappings checked.',
        'Existing dispatcher aliases real-mode PCs; no second dispatcher or original callee substitution.',
        'Final-state emulator comparison, not physical memory-protection faults/MI interrupts/cycle-exact CPU enforcement or full game.']}, indent=2) + '\n')
print('PASS16whole compiled memory-protection calls/24scalars/32BAT words/table/queue;26state-preserving guards')
