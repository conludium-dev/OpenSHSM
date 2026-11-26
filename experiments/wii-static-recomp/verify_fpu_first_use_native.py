"""Compare native vector/handler/retry execution with the original lazy-FPU captures."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'fpu-first-use-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['returnCode'] == 0 and build['builderSha256'] == sha(experiment / 'build_fpu_first_use_native.py')
assert build['baseBootSha256'] == sha(private / 'mass-ai-clock-boot/boot.json')
assert build['oracleSha256'] == sha(private / 'dolphin-fpu-lazy/comparison.json')
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
for name, digest in build['headerHashes'].items():
    assert sha(experiment / name) == digest
assert len(build['records']) == 125
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if 'inputSource' in row and row['file'] in ('output_1.cpp', 'output_63.cpp', 'main_output.cpp'):
        assert sha(Path(row['inputSource'])) == row['inputSourceSha256']
        text = Path(row['inputSource']).read_text()
        for change in build['changes']:
            if change['file'] == row['file']:
                assert text.count(change['before']) == 1
                text = text.replace(change['before'], change['after'])
        assert text == Path(row['source']).read_text()
ghidra_path = private / 'dolphin-fpu-lazy/ghidra/verification.json'
ghidra = json.loads(ghidra_path.read_text())
for row in ghidra['records']:
    assert row['objectSha256'] == sha(private / 'dtk-output/obj/auto_03_802045CC_text.o')
    assert row['assemblySha256'] == sha(ghidra_path.parent / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(ghidra_path.parent / (row['name'] + '.c'))
    if row['name'] != '__OSLoadFPUContext':
        assert row['discoveredBodyBytes'] == row['bytes']
oracle = json.loads((private / 'dolphin-fpu-lazy/comparison.json').read_text())
capture = json.loads((private / 'dolphin-fpu-lazy/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data = base64.b64decode(capture['data'])
exe = output / 'fpu-first-use-probe'
assert sha(exe) == build['executableSha256']
fresh = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
assert fresh.returncode == 0 and not fresh.stderr
import struct
for text in ((output / 'native.log').read_text(), fresh.stdout):
    lines = text.splitlines()
    assert len(lines) == 32
    for index in range(16):
        expected = oracle['states'][index][:10] + [0x807f0000, int(index % 2 == 0)]
        assert lines[index * 2] == 'FPU_CASE ' + ' '.join(map(str, [index] + expected))
        row = data[index * 736:(index + 1) * 736]
        payload = []
        for offset in range(0, 128, 4):
            payload.extend([struct.unpack_from('>I', row, 128 + offset)[0], struct.unpack_from('>I', row, 256 + offset)[0]])
        assert lines[index * 2 + 1] == 'FPU_COPY ' + ' '.join(map(str, [index] + payload))
guards = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'], capture_output=True, text=True, timeout=30)
assert guards.returncode == 0 and guards.stdout == 'FPU_GUARDS 10\n' and not guards.stderr
invalid = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'invalid'], capture_output=True, text=True, timeout=30)
assert invalid.returncode == 2 and not invalid.stdout and not invalid.stderr
(output / 'comparison.json').write_text(json.dumps({'result': 'COMPILED_ORIGINAL_FPU_VECTOR_HANDLER_RETRY8_CONTROLS8_COPY_ABI_MATCH',
    'buildSha256': sha(output / 'build.json'), 'verifierSha256': sha(Path(__file__)), 'oracleSha256': build['oracleSha256'],
    'ghidraSha256': sha(ghidra_path), 'guards': 10, 'limits': ['Native return sentinel807F0000 replaces fixture call-return addresses.',
        'Empty context/owner0 first-use only; no prior-owner/populated FPU restoration/physical timing/full registers or retail boot proof.']}, indent=2) + '\n')
print('PASS native original vector→FPU handler→exact retry:8lazy/8enabled copies and10unsupported profiles refuse')
