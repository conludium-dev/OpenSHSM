"""Compare compiled syscall/vector/cache execution with the original captured states."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'flush-syscall-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['returnCode'] == 0 and build['builderSha256'] == sha(experiment / 'build_flush_syscall_native.py')
assert build['baseBootSha256'] == sha(private / 'mass-fpu-boot/boot.json')
assert build['oracleSha256'] == sha(private / 'dolphin-flush-syscall/comparison.json')
for path, digest in {**build['sourceHashes'], **build['inputHashes']}.items():
    assert sha(Path(path)) == digest
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
for before, after in build['transforms']:
    address, opcode = [int(value, 16) for value in before.splitlines()[0].strip().removeprefix('// 0x').split(': ')]
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
assert len(build['records']) == 125
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] == 'output_63.cpp':
        assert sha(Path(row['inputSource'])) == row['inputSourceSha256']
        text = Path(row['inputSource']).read_text()
        for before, after in build['transforms']:
            assert text.count(before) == 1
            text = text.replace(before, after)
        assert text == Path(row['source']).read_text()
ghidra_path = private / 'dolphin-flush-syscall/ghidra/verification.json'
ghidra = json.loads(ghidra_path.read_text())
for row in ghidra['records']:
    assert row['discoveredBodyBytes'] == row['bytes']
    assert row['objectSha256'] == sha(private / 'dtk-output/obj/auto_03_802045CC_text.o')
    assert row['assemblySha256'] == sha(ghidra_path.parent / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(ghidra_path.parent / (row['name'] + '.c'))
oracle = json.loads((private / 'dolphin-flush-syscall/comparison.json').read_text())
capture = json.loads((private / 'dolphin-flush-syscall/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
exe = output / 'flush-syscall-probe'
assert sha(exe) == build['executableSha256']
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
assert result.returncode == 0 and not result.stderr
for text in ((output / 'native.log').read_text(), result.stdout):
    lines = text.splitlines()
    assert len(lines) == 32
    for index in range(16):
        nonzero = index % 8 != 0
        expected = oracle['states'][index][:12] + [0x807f0000, int(nonzero), int(nonzero)]
        assert lines[index * 2] == 'FLUSH_CASE ' + ' '.join(map(str, [index] + expected))
        memory = struct.unpack_from('>40I', data, index * 736 + 128)
        assert lines[index * 2 + 1] == 'FLUSH_MEMORY ' + ' '.join(map(str, [index, *memory]))
guards = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'], capture_output=True, text=True, timeout=30)
assert guards.returncode == 0 and guards.stdout == 'FLUSH_GUARDS 12\n' and not guards.stderr
invalid = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'invalid'], capture_output=True, text=True, timeout=30)
assert invalid.returncode == 2 and not invalid.stdout and not invalid.stderr
(output / 'comparison.json').write_text(json.dumps({'result': 'COMPILED_DCFLUSH16_ORIGINAL_SYSCALL14_CACHE_VISIBILITY_MATCH',
    'buildSha256': sha(output / 'build.json'), 'verifierSha256': sha(Path(__file__)), 'oracleSha256': build['oracleSha256'],
    'ghidraSha256': sha(ghidra_path), 'guards': 12, 'limits': ['Native return sentinel replaces fixture caller addresses.',
        'HID0 bit8 uses existing CPU storage; host sequential fence is a PC barrier adaptation, isync has no host cache-flush effect.',
        'D-cache writeback is synchronous in the existing model; no physical hardware ordering/timing/full registers or retail boot proof.']}, indent=2) + '\n')
print('PASS16native original flush/syscall/cache states +12unsupported or missing-barrier transitions refuse')
