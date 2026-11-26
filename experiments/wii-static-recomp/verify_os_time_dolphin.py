"""Compare original OS consumer against the full native module using observed raw ticks."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-os-time-probe')
native = Path('work/private-game/static-recomp/mass-timebase-active')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 64 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_os_time_dolphin.ps1')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_os_time_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
assert generation['originalSha256'] == sha(original_path)
header = struct.unpack('>64I', original[:256])
endpoint = 0x8021c014
section = next(i for i in range(18) if header[18 + i] <= endpoint < header[18 + i] + header[36 + i])
offset = header[section] + endpoint - header[18 + section]
image = (output / 'fpr-init.dol').read_bytes()
assert {i for i in range(256, len(original)) if image[i] != original[i]} <= set(range(offset, offset + 4))
data = base64.b64decode(capture['data'])
assert len(data) == 64 * 736
inputs, expected = [], []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    tick = struct.unpack_from('>Q', row, 24)[0]
    gpr = list(struct.unpack_from('>32I', row, 32))
    cr, lr, ctr, xer, hid2, hid0, msr = struct.unpack_from('>7I', row, 160)
    assert gpr[1] == 0x80540000 and lr == record['expectedLr'] and msr == 0x2030
    assert all(gpr[index] == 0x12340000 + index * 0x100 for index in range(14, 32))
    assert (gpr[3] << 32 | gpr[4]) == (tick + record['adjustment']) & ((1 << 64) - 1)
    inputs.append((tick, record['adjustment']))
    expected.append([gpr[3], gpr[4], 1, msr, xer, cr, 3])
build = json.loads((native / 'os-time-build.json').read_text())
assert build['executableSha256'] == sha(native / 'os-time-probe')
assert build['wrapperSha256'] == sha(native / 'os-time-wrapper.cpp')
assert build['probeHeaderSha256'] == sha(experiment / 'os_time_probe.h')
assert build['scriptSha256'] == sha(experiment / 'build_os_time_probe.py')
assert build['baseLoweringSha256'] == sha(Path('work/private-game/static-recomp/mass-timebase/lowering.json'))
result = subprocess.run([str(native / 'os-time-probe'), '--os-time-check'], input=''.join(f'{tick} {adjustment}\n' for tick, adjustment in inputs),
                        capture_output=True, text=True, timeout=30)
(native / 'os-time-dolphin-native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stdout[-1000:], result.stderr)
actual = [list(map(int, line.split())) for line in result.stdout.splitlines()]
assert actual == expected
report = {'result': 'ORIGINAL_OS_TIME_DOLPHIN_CONSUMER_MATCH', 'cases': 64, 'adjustmentVariants': 8,
          'observedClockSource': 'Original TBR instructions in Dolphin; raw reader return observed before adjustment.',
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'nativeBuildSha256': sha(native / 'os-time-build.json'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Original OS consumer executes with Dolphin Wii MMU; native receives the same observed raw tick.',
                     'Reader BLR replaced with a disclosed register/flag-preserving store/BLR observer; not unmodified retail boot.',
                     'MSR.EE=0, supplied adjustment input; no PC clock epoch/rate synchronization or interrupt-enabled delivery proof.']}
(native / 'os-time-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS original Dolphin OS-time consumer:64observations/8offsets/result-XER-CR/MSR/ABI; PC clock epoch remains unverified')
