"""Compare independent accurate-cache conflict traces; refuse broader cache acceptance."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-conflict-probe')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == 8 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_conflict_probe.ps1')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_conflict_probe.py')
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(dol_path)
original = dol_path.read_bytes()
words = struct.unpack('>64I', original[:256])
address = 0x80212f80
section = next(index for index in range(18) if words[18 + index] <= address < words[18 + index] + words[36 + index])
offset = words[section] + address - words[18 + section]
assert base64.b64decode(capture['originalDceCode']) == original[offset:offset + 20]
assert (output / 'fpr-init.dol').read_bytes()[offset:offset + 20] == original[offset:offset + 20]
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
data = base64.b64decode(capture['data'])
assert len(data) == 8 * 736
observed = []
for trial in range(8):
    record = data[trial * 736:(trial + 1) * 736]
    assert record[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>II', record, 16) == (0xc001cafe, trial)
    observed.append(list(struct.unpack_from('>20I', record, 32)))
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
exe = output / 'conflict-native'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(upstream / 'nWiiRuntime/include'),
                         str(experiment / 'conflict_native.cpp'), str(experiment / 'processor_adapter.cpp'), '-o', str(exe)],
                        capture_output=True, text=True, timeout=30)
(output / 'native-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
native = [list(map(int, line.split())) for line in result.stdout.splitlines()]
assert len(native) == 8
for trial, (row, expected) in enumerate(zip(native, observed)):
    assert row == [trial, *expected], (trial, row, expected)
    assert sum(value == 0x2000 + index for index, value in enumerate(expected[:10])) == 1
    assert sum(value == 0x2000 + index for index, value in enumerate(expected[10:])) == 2
report = {'result': 'ACCURATE_CACHE_CONFLICT_TRACE_MATCH', 'trials': 8, 'samples': 160,
          'patterns': generation['patterns'], 'observed': observed, 'native': [row[1:] for row in native],
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'frontendSha256': sha(experiment / 'memory_frontend.h'), 'nativeSourceSha256': sha(experiment / 'conflict_native.cpp'),
          'nativeSupportSha256': sha(experiment / 'memory_frontend_probe.cpp'), 'executableSha256': sha(exe),
          'verifierSha256': sha(Path(__file__)),
          'limits': ['Eight synthetic MEM1 dirty conflict-set trials; not exhaustive replacement, cache-op, DMA or locked-cache validation.',
                     'Original DCEnable executed in Dolphin; native test supplies DCE and does not prove original cache-enabled boot.',
                     'No physical Wii, OS/IOS/GX/menu/game acceptance.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS accurate-cache independent conflict trace:8trials/160samples; broader DCE boot pending')
