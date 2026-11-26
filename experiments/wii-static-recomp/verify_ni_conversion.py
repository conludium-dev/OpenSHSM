"""Verify numerical NI conversion only; flags and full runtime activation remain pending."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-ni-probe')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 32 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_ni_dolphin.ps1')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_ni_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
assert sha(original_path) == generation['originalSha256']
image = (output / 'fpr-init.dol').read_bytes()
offset = generation['exitPatchOffset']
assert {index for index in range(256, len(original)) if original[index] != image[index]} <= set(range(offset, offset + 4))
assert struct.unpack_from('>I', original, offset - 4)[0] == generation['frspOpcode']
data = base64.b64decode(capture['data'])
assert len(data) == 32 * 736
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    pre = struct.unpack_from('>Q', row, 24)[0] & 0xffffffff
    assert pre == record['ni'] * 4
    destination = generation['frspDestination']
    ps0 = struct.unpack_from('>Q', row, 192 + destination * 8)[0]
    ps1 = struct.unpack_from('>Q', row, 448 + destination * 8)[0]
    assert ps0 == ps1
    post = struct.unpack_from('>Q', row, 704)[0] & 0xffffffff
    observations.append({'index': index, 'inputBits': record['inputBits'], 'ni': record['ni'],
                         'resultDoubleBits': ps0, 'fpscrBefore': pre, 'fpscrAfter': post})
exe = output / 'ni-conversion-probe'
result = subprocess.run(['clang++', '-std=c++20', '-O2', '-I', str(experiment), str(experiment / 'ni_conversion_probe.cpp'), '-o', str(exe)],
                        capture_output=True, text=True, timeout=30)
(output / 'conversion-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
inputs = [(record['inputBits'], record['ni']) for record in observations]
inputs.extend([(0x7ff8000000000001, 0), (0x7ff0000000000001, 1)])
result = subprocess.run([str(exe)], input=''.join(f'{value} {ni}\n' for value, ni in inputs), capture_output=True, text=True, timeout=30)
(output / 'conversion-native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0
rows = result.stdout.splitlines()
assert len(rows) == 34 and rows[-2:] == ['REFUSED', 'REFUSED']
for row, record in zip(rows[:32], observations):
    single, widened = map(int, row.split())
    assert widened == record['resultDoubleBits'], (record, hex(single), hex(widened))
assert observations[8]['resultDoubleBits'] == 0x3810000000000000
assert observations[24]['resultDoubleBits'] == 0
report = {'result': 'NI_NUMERIC_CONVERSION_MATCH_FPSCR_RUNTIME_UNVERIFIED', 'numericCases': 32, 'nanRefusals': 2,
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'headerSha256': sha(experiment / 'ni_conversion.h'), 'probeSha256': sha(experiment / 'ni_conversion_probe.cpp'),
          'verifierSha256': sha(Path(__file__)), 'observations': observations,
          'limits': ['Original NI setter and original-address frsp execute with RN0; exit observer after frsp is disclosed.',
                     'Numerical PS0/PS1 values compared; FPSCR output fields retained as observations but not reproduced by the numerical core.',
                     'Finite/infinity RN0 profile only; NaN payloads/exceptions, RN1..3 and other scalar/paired/FMA operations pending.',
                     'Integer-only conversion core is not wired into generated FP instructions; live NI gate stays closed, no full boot acceptance.']}
(output / 'conversion-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS NI numeric32cases/2NaNrefusals; minnormal pre-round flush verified; FPSCR/full FP/runtime NI gate pending')
