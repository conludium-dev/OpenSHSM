"""Collect original lazy-FPU handler evidence; do not force FP enable or claim a boot fix."""
from pathlib import Path
import hashlib
import json
import re
import struct

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
sites = []
for address, expected in [(0x8020AFD4, 0xDBE10070), (0x80213DC0, 0x7CA000A6),
    (0x80213DC4, 0x60A52000), (0x80213DC8, 0x7CA00124), (0x80213DD4, 0x60A52000),
    (0x80213DD8, 0x7CBB03A6), (0x80213DE0, 0x80A300D8), (0x80213DE4, 0x908300D8),
    (0x80213DF8, 0x4BFFF8F9), (0x80213DFC, 0x4BFFF7C5)]:
    section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    word = struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0]
    assert word == expected
    sites.append({'address': hex(address), 'word': hex(word)})
text = (root / 'window-thp-dcbz/output_37.cpp').read_text()
start, end = text.index('loc_8020AFD0: ;'), text.index('loc_8020AFD8: ;')
prefix = text[start:end]
assert 'ctx.mmu.write_f64(ctx.gpr[1] + 112, ctx.fpr[31]);' in prefix
assert 'ctx.msr' not in prefix and 'process_pending_callbacks' not in prefix
interpreter = (root / 'window-quantization/interpreter.cpp').read_text()
assert re.search(r'case 54: ctx.mmu.write_f64\(ea_ra0\(simm\), ctx.fpr\[rD\]\); break;', interpreter)
fixtures = []
for path in sorted(root.glob('window-idct-fixtures-blocks120-thp-block*.txt')):
    header = list(map(int, path.read_text().splitlines()[0].split()))
    assert header[0] == 0x8020AFD0
    fixtures.append({'file': path.name, 'sha256': sha(path), 'msr': hex(header[4]), 'fpEnabled': bool(header[4] & 0x2000)})
assert len(fixtures) == 3 and not any(row['fpEnabled'] for row in fixtures)
report = {'result': 'ORIGINAL_LAZY_FPU_AND_NATIVE_GUARD_OMISSION_EVIDENCE', 'dolSha256': sha(dol_path),
    'sites': sites, 'fixtures': fixtures, 'guestSourceSha256': sha(root / 'window-thp-dcbz/output_37.cpp'),
    'interpreterSha256': sha(root / 'window-quantization/interpreter.cpp'),
    'primaryReferences': [
        'https://raw.githubusercontent.com/dolphin-emu/dolphin/master/Source/Core/Core/PowerPC/Interpreter/Interpreter.cpp',
        'https://raw.githubusercontent.com/dolphin-emu/dolphin/master/Source/Core/Core/PowerPC/PowerPC.cpp'],
    'limits': ['Native first stfd executes without MSR.FP guard; original handler enables FP and switches owner at800000D8.',
        'Dolphin reference raises unavailable exception before instruction when FP0; current instruction re-executed after handler.',
        'No actual original-FPU exception trace captured and no FPU guard implemented yet.',
        'Cause of pixel corruption/boot delays remains inferred, not accepted; do not force MSR.FP as a workaround.']}
(root / 'fp-unavailable-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 'fixturesFP0=', len(fixtures), 'DOLsites=', len(sites))
