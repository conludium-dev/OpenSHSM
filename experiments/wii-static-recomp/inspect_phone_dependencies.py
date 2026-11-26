"""Inventory direct calls from own DOL, independently of generated C++ and HLE labels."""
from pathlib import Path
import hashlib
import json
import re
import struct

private = Path('work/private-game/static-recomp')
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
catalogue = {}
for row in (private / 'nwii-current/nwii-functions.tsv').read_text().splitlines():
    start, end, count, hle = row.split('\t')
    catalogue[int(start, 16)] = (int(end, 16), int(count), hle)
dtk = {}
for path in (private / 'dtk-output/asm').glob('*.s'):
    for start, size in re.findall(r'# \.text:0x[0-9A-Fa-f]+ \| 0x([0-9A-Fa-f]+) \| size: 0x([0-9A-Fa-f]+)', path.read_text()):
        dtk[int(start, 16)] = (int(size, 16), str(path))


def original_word(address):
    index = next(index for index in range(18) if header[18 + index] <= address < header[18 + index] + header[36 + index])
    return struct.unpack_from('>I', dol, header[index] + address - header[18 + index])[0]


def inspect(start):
    end, count, hle = catalogue[start]
    size, assembly = dtk[start]
    dtk_end = start + size
    direct = []
    indirect = []
    paired = []
    for address in range(start, dtk_end, 4):
        word = original_word(address)
        if word >> 26 == 18:
            displacement = word & 0x3fffffc
            if displacement & 0x2000000:
                displacement -= 0x4000000
            target = (displacement if word & 2 else address + displacement) & 0xffffffff
            if word & 1 or not start <= target < dtk_end:
                direct.append({'instruction': hex(address), 'target': hex(target), 'link': bool(word & 1)})
        if word >> 26 == 19 and (word >> 1) & 1023 == 528:
            indirect.append(hex(address))
        if word >> 26 in (4, 56, 57, 60, 61):
            paired.append(hex(address))
    return {'address': hex(start), 'dtkEnd': hex(dtk_end), 'analyzerEnd': hex(end), 'bytes': size, 'analyzerInstructions': count,
            'boundaryAgreement': dtk_end == end, 'instructionCountMatchesBoundary': count * 4 == size,
            'dtkAssembly': assembly, 'automaticHleLabel': hle, 'directCallsOrExternalBranches': direct,
            'indirectCtrBranches': indirect, 'pairedSingleInstructions': paired}


roots = [0x800f3d94, 0x800f3e30, 0x800f3e60, 0x800f3ec0]
root_records = [inspect(start) for start in roots]
callees = sorted({int(call['target'], 16) for record in root_records for call in record['directCallsOrExternalBranches']})
callee_records = [inspect(start) for start in callees]
analyzer_path = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiAnalyzer/src/analyzer.cpp')
analyzer_source = analyzer_path.read_text()
assert '(inst.value() & 0x3FF) == 528' in analyzer_source
assert 'uint32_t spr = (inst.value() >> 11) & 0x3FF' in analyzer_source
bctr_word = original_word(0x800ed410)
mtctr_word = original_word(0x800ed40c)
assert bctr_word == 0x4e800420 and mtctr_word == 0x7c8903a6
switch_targets = [original_word(0x803f0608 + index * 4) for index in range(31)]
assert all(0x800ed3c8 <= address < 0x800ed8c8 for address in switch_targets)
assert ((bctr_word >> 1) & 1023) == 528 and (bctr_word & 1023) != 528
correct_spr = ((mtctr_word >> 16) & 31) | (((mtctr_word >> 11) & 31) << 5)
assert correct_spr == 9 and ((mtctr_word >> 11) & 1023) != 9
switch_check = {'originalBctrInstruction': '0x800ed410', 'originalBctrWord': hex(bctr_word),
                'correctExtendedOpcode': (bctr_word >> 1) & 1023,
                'upstreamComparedValue': bctr_word & 1023, 'upstreamBctrDetectionMatches': False,
                'originalMtctrInstruction': '0x800ed40c', 'correctSpr': correct_spr,
                'upstreamComparedSpr': (mtctr_word >> 11) & 1023,
                'jumpTableAddress': '0x803f0608', 'entries': 31, 'originalTargets': [hex(address) for address in switch_targets],
                'analyzerSource': str(analyzer_path), 'analyzerSourceSha256': hashlib.sha256(analyzer_path.read_bytes()).hexdigest(),
                'classification': 'Original DOL words/table plus evaluated pinned upstream bit masks; no vendor source changed.'}
report = {'result': 'PASS', 'dolSha256': hashlib.sha256(dol).hexdigest(), 'roots': root_records, 'directCallees': callee_records,
          'switchDetectionCheck': switch_check,
          'classification': {'originalEvidence': 'Direct-call opcodes and dtk/NWii boundary agreement from supported own Wii DOL.',
                             'inferredBehavior': 'Phone callback names from existing source UI research; audio/GUI callee roles require consumer verification.',
                             'pcAdaptation': 'Only vibrate currently connected to experimental native PhoneUI.'},
          'limits': ['Static immediate-callee inventory, not complete transitive/dynamic call graph or behavior verification.',
                     'Paired-single/indirect branch presence blocks claims based only on successful C++ compilation.',
                     'Ringtone null-host branch alone would omit non-null service effects; do not claim whole handler acceptance.']}
(private / 'phone-dependencies.json').write_text(json.dumps(report, indent=2) + '\n')
disagreements = [record['address'] for record in root_records + callee_records
                 if not record['boundaryAgreement'] or not record['instructionCountMatchesBoundary']]
print('PASS:inventory only;', len(root_records), 'phone roots,', len(callee_records), 'direct callees; analyzer discrepancies:', disagreements)
