"""Verify FRSP PS0/PS1 and complete FPSCR against independent sticky-state observations."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-frsp-flags')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 256 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_frsp_flags_dolphin.ps1')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_frsp_flags_dolphin.py')
assert generation['baseGeneratorSha256'] == sha(experiment / 'build_ni_dolphin.py')
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
assert len(data) == 256 * 736
observations = []
destination = generation['frspDestination']
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    pre = struct.unpack_from('>Q', row, 24)[0] & 0xffffffff
    initial = record['initialFpscr'] & 0xfffff7ff
    initial = (initial & ~0x60000000) | (0x20000000 if initial & 0x01f80700 else 0) | record['ni'] * 4
    assert pre == initial
    observations.append({'index': index, 'inputBits': record['inputBits'], 'fpscrBefore': pre,
                         'ps0': struct.unpack_from('>Q', row, 192 + destination * 8)[0],
                         'ps1': struct.unpack_from('>Q', row, 448 + destination * 8)[0],
                         'fpscrAfter': struct.unpack_from('>Q', row, 704)[0] & 0xffffffff})
exe = output / 'frsp-probe'
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
result = subprocess.run(['clang++', '-std=c++20', '-O2', '-I', str(experiment), '-I', str(upstream / 'nWiiRuntime/include'),
                         str(experiment / 'frsp_probe.cpp'), '-o', str(exe)], capture_output=True, text=True, timeout=30)
(output / 'native-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
inputs = [(record['inputBits'], record['fpscrBefore'], generation['frspOpcode']) for record in observations]
inputs += [(0x7ff8000000000001, 0, generation['frspOpcode']), (0x7ff0000000000001, 4, generation['frspOpcode'])]
inputs += [(0x3ff0000000000000, fpscr, generation['frspOpcode']) for fpscr in [1, 2, 3, 8, 128, 0x800]]
result = subprocess.run([str(exe)], input=''.join(f'{bits} {fpscr} {opcode}\n' for bits, fpscr, opcode in inputs),
                        capture_output=True, text=True, timeout=30)
(output / 'native-results.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = result.stdout.splitlines()
assert len(rows) == 264 and rows[-8:] == ['REFUSED'] * 8
mismatches = []
for line, record in zip(rows[:256], observations):
    actual = list(map(int, line.split()))
    expected = [record['ps0'], record['ps1'], record['fpscrAfter'], 0xaaaaaaaa, 1]
    if actual != expected:
        mismatches.append({'observation': record, 'actual': actual, 'expected': expected})
if mismatches:
    (output / 'mismatches.json').write_text(json.dumps(mismatches, indent=2) + '\n')
assert not mismatches, mismatches[:3]
report = {'result': 'FRSP_RN0_FINITE_INFINITY_PS0_PS1_FPSCR_ORIGINAL_MATCH', 'cases': 256, 'refusalRollbackCases': 8,
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'adapterSha256': sha(experiment / 'frsp_adapter.h'), 'conversionSha256': sha(experiment / 'ni_conversion.h'),
          'probeSha256': sha(experiment / 'frsp_probe.cpp'), 'verifierSha256': sha(Path(__file__)),
          'observations': observations,
          'limits': ['Original-address non-record frsp, RN0 finite/infinity profile, NI0/NI1 and eight sticky-state seeds.',
                     'NaN/other rounding/enabled exception profiles refuse with unchanged FPR/FPSCR; native preservation checked.',
                     'Other FP/paired/FMA operations and NI live activation remain unverified; not full FPU/physical-console proof.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS FRSP256original cases:PS0/PS1/FPSCR/sticky-state preservation;8refusals; NI full runtime pending')
