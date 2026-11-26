"""Compare original PPC executed by Dolphin with the translated native CPU fixture."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import re
import struct
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--icache', action='store_true')
args = parser.parse_args()
experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-icache-probe' if args.icache else 'work/private-game/static-recomp/dolphin-probe')
native = Path('work/private-game/static-recomp/mass-icache' if args.icache else 'work/private-game/static-recomp/mass-fpscr-translated')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
assert generation['originalSha256'] == hashlib.sha256(original).hexdigest()
assert generation['scriptSha256'] == sha(experiment / 'build_dolphin_probe.py')
header = struct.unpack('>64I', original[:256])
code_section = next(index for index in range(18) if header[18 + index] <= 0x80210890 < header[18 + index] + header[36 + index])
offset = header[code_section] + 0x80210890 - header[18 + code_section]
original_fpr = original[offset:offset + 0x128]
captures = {}
for record in generation['records']:
    image = (output / record['file']).read_bytes()
    assert record['sha256'] == hashlib.sha256(image).hexdigest()
    changes = {index for index in range(256, len(original)) if image[index] != original[index]}
    allowed = set()
    for patch in record['patches']:
        address = int(patch['address'], 16)
        section = next(index for index in range(18) if header[18 + index] <= address < header[18 + index] + header[36 + index])
        location = header[section] + address - header[18 + section]
        assert struct.unpack_from('>I', original, location)[0] == int(patch['original'], 16)
        assert struct.unpack_from('>I', image, location)[0] == int(patch['measurementBranch'], 16)
        allowed.update(range(location, location + 4))
    assert changes <= allowed
    mode = Path(record['file']).stem
    capture = json.loads((output / (mode + '-dolphin.json')).read_text(encoding='utf-8-sig'))
    assert capture['harnessSha256'].lower() == record['sha256']
    assert capture['emulatorSha256'].lower() == sha(Path('work/research/dolphin/Dolphin-x64/Dolphin.exe'))
    assert 'Dolphin.Core.CPUCore=0' in capture['arguments'] and 'Dolphin.Core.DualCore=False' in capture['arguments']
    assert base64.b64decode(capture['originalFprCode']) == original_fpr
    raw = base64.b64decode(capture['data'])
    assert len(raw) == record['records'] * 736
    rows = [raw[index * 736:(index + 1) * 736] for index in range(record['records'])]
    for index, row in enumerate(rows):
        assert row[:16] == b'OSHSM_PPC_DLP001'
        assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    captures[mode] = (capture, rows)
boot = json.loads((native / 'boot.json').read_text())
assert boot['executableSha256'] == sha(native / 'openshsm-mass-boot')
assert boot['wrapperSha256'] == sha(experiment / ('icache_boot.cpp' if args.icache else 'fpscr_boot.cpp'))
assert boot['baseWrapperSha256'] == sha(experiment / 'mass_boot.cpp')
if args.icache:
    assert boot['fpscrWrapperSha256'] == sha(experiment / 'fpscr_boot.cpp')
boundary = '80212f80' if args.icache else '802130e0'
expected_lr = 0x802134c8 if args.icache else 0x802134ac
assert f'BOOT_BOUNDARY pc={boundary} lr={expected_lr:x} msr=2030' in boot['stdout']
capture, rows = captures['boot']
row = rows[0]
gpr = list(struct.unpack_from('>32I', row, 32))
assert gpr == list(map(int, re.search(r'BOOT_REGISTERS((?: \d+){32})', boot['stdout'])[1].split()))
cr, lr, ctr, xer, hid2, hid0, msr = struct.unpack_from('>7I', row, 160)
assert (lr, ctr, xer, hid2, hid0, msr) == (expected_lr, 0, 0, 0xa0000000, 0x8000 if args.icache else 0, 0x2030)
state = [list(map(int, line.split()[1:])) for line in boot['stdout'].splitlines() if line.startswith('FP_STATE ')][-1]
assert cr == sum(value << ((7 - index) * 4) for index, value in enumerate(state[2:10]))
assert [ctr, xer] == state[74:76]
assert (struct.unpack_from('>Q', row, 704)[0] & 0xffffffff) == state[1]
assert list(struct.unpack_from('>32Q', row, 192)) == state[10:42]
assert list(struct.unpack_from('>32Q', row, 448)) == state[42:74]
assert base64.b64decode(capture['stack']) == bytes(map(int, re.search(r'BOOT_STACK((?: \d+){64})', boot['stdout'])[1].split()))
result = subprocess.run([str(native / 'openshsm-mass-boot'), '--fpr-init-check', 'work/private-game/disc/DATA/sys/main.dol'],
                        capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
(output / 'translated-native-initializer.log').write_text(result.stdout + result.stderr)
native_rows = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines()]
assert len(native_rows) == 8
for mode, (row, values) in enumerate(zip(captures.get('fpr-init', (None, []))[1], native_rows)):
    assert values[:4] == [mode, 0x807f0000, 0x2030, 0]
    assert struct.unpack_from('>I', row, 184)[0] == values[2]
    assert (struct.unpack_from('>Q', row, 704)[0] & 0xffffffff) == values[3]
    assert list(struct.unpack_from('>32Q', row, 192)) == values[4:36], mode
    assert list(struct.unpack_from('>32Q', row, 448)) == values[36:], mode
report = {'result': 'PASS_WITH_SCOPE_LIMITS', 'bootGprCrLrCtrXerMsrHid2Hid0FprPs1FpscrStackMatch': True,
          'originalInitializerCases': 0 if args.icache else 8, 'pairedOriginalCases': 0 if args.icache else 4, 'registerHalvesPerCase': 64,
          'measurementBoundary': '0x80212F8C/before DCEnable mtspr' if args.icache else '0x802130EC/before ICEnable mtspr',
          'nativeFunctionPC': '0x' + boundary.upper(),
          'nativeExeSha256': sha(native / 'openshsm-mass-boot'), 'nativeBootReportSha256': sha(native / 'boot.json'),
          'generationSha256': sha(output / 'generation.json'), 'scriptSha256': sha(Path(__file__)),
          'captureSha256': {mode: sha(output / (mode + '-dolphin.json')) for mode in captures},
          'limits': ['Dolphin 2609 Wii interpreter under Windows ARM/x64 emulation, not physical Wii hardware.',
                     'Private measurement DOL: synthetic initialization and collector; original boot stop instruction replaced with a non-linking branch after its preceding instructions.',
                     'Initial MSR IR/DR=0x30 with Dolphin boot MMU setup; native flat-MMU cached-address adapter verified only for this prefix.',
                     'Collector saves r12 via SPRG3 and enables PSE after the original callee to read PS1; observer effects are outside compared state.',
                     'Logical ICE readback only for immutable code; no physical cache timing/dynamic code/data-cache/OS/IOS/GX/audio/controller/menu/scene acceptance.',
                     'Arbitrary FI/reserved-bit disagreement is not resolved by the zero-FPSCR boot/initializer cases.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS scoped Dolphin comparison:', 'ICE enabled; next DCEnable' if args.icache else 'PS1/stack and8 original FPR initializer cases; next ICEnable')
