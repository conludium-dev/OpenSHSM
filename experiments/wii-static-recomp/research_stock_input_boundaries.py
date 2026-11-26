"""Retain local Wii SDK input anchors and callers privately; semantic labels remain explicitly inferred."""
from pathlib import Path
import hashlib
import json
import struct
import sys

sys.path.insert(0, 'work/research')
from wii_reader import listing
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
header = struct.unpack('>64I', dol[:256])
def read(address, size):
    section = next(i for i in range(18) if header[18 + i] <= address
        and address + size <= header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    return dol[offset:offset + size]
anchors = {0x80447780: 'WPADInit()', 0x80447888: 'WARNING: Overwritten the callback needed by KPAD.',
    0x804478BC: '         Please call KPADSetSamplingCallback instead of WPADSetSamplingCallback.',
    0x80447910: '         Please call KPADSetConnectCallback instead of WPADSetConnectCallback.'}
for address, text in anchors.items():
    assert read(address, len(text)) == text.encode()
targets = {0x80280AC0: 'channel-state/type query (WPADProbe inferred)',
    0x8027AAC0: 'sample read wrapper (KPADRead inferred)',
    0x80280B50: 'sampling callback setter inferred from warning string/callback slot8A8',
    0x80280BE0: 'connect callback setter inferred from warning string/callback slot8A4'}
callers = {f'{address:08X}': [] for address in targets}
for i in range(7):
    offset, base, size = header[i], header[18 + i], header[36 + i]
    for position in range(offset, offset + size - 3, 4):
        word = struct.unpack_from('>I', dol, position)[0]
        if word >> 26 != 18 or word & 2:
            continue
        delta = word & 0x3FFFFFC
        if delta & (1 << 25):
            delta -= 1 << 26
        pc = base + position - offset
        target = (pc + delta) & 0xFFFFFFFF
        if target in targets:
            callers[f'{target:08X}'].append(f'{pc:08X}')
assert '8018E354' in callers['80280AC0'] and '8018E370' in callers['8027AAC0']
assert read(0x80280BB0, 4) == struct.pack('>I', 0x93BF08A8)
assert read(0x80280C40, 4) == struct.pack('>I', 0x93BF08A4)
assert read(0x8018E358, 4) == struct.pack('>I', 0x907E0000)
fragments = [(0x8018E2E0, 0xB0), (0x80280AC0, 140), (0x80280B50, 136),
    (0x80280BE0, 136), (0x8027AAC0, 0x180)]
output = Path('work/private-game/static-recomp/stock-baseline/wpad-probe-research')
output.mkdir(exist_ok=True)
report = {'result': 'OWN_WII_INPUT_BOUNDARY_RESEARCH', 'dolSha256': sha(dol_path),
    'recipeSha256': sha(Path(__file__)), 'originalStringAnchors': {f'{a:08X}': text for a, text in anchors.items()},
    'inferredNames': {f'{a:08X}': text for a, text in targets.items()}, 'directBranchCallers': callers,
    'originalListings': {f'{a:08X}': listing(a, size) for a, size in fragments},
    'limits': ['Addresses, opcode/string anchors and direct relative callers are original own-DOL evidence.',
        'SDK semantic function names inferred, no original debug symbol table.',
        'No matching-only dataflow claim from lis/addi string candidates; channel query separately executed192cases.',
        'Sample buffer format, lifecycle/sampling/connect callbacks and actual warning predicate remain unverified.']}
(output / 'boundaries.json').write_text(json.dumps(report, indent=2) + '\n')
print('OWN_WII_INPUT_BOUNDARY_RESEARCH', json.dumps(callers))
