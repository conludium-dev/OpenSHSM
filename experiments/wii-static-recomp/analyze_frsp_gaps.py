"""Inspect raw FRSP candidates missing from generated IR without inventing functions."""
from pathlib import Path
import hashlib
import json
import struct
import sys

sys.path.insert(0, 'work/research/macos-python-libs' if sys.platform == 'darwin' else 'work/research/python-libs')
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

private = Path('work/private-game/static-recomp')
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
audit = json.loads((private / 'mass-frsp/audit.json').read_text())
missing = [int(address, 16) for address in audit['untranslatedAddresses']]
header = struct.unpack('>64I', original[:256])
sections = [(index, header[index], header[18 + index], header[36 + index])
            for index in range(18) if header[36 + index]]
catalogue_path = private / 'mass-current/functions.tsv'
catalogue = [[int(value, 16) for value in row.split('\t')[:3]] for row in catalogue_path.read_text().splitlines()]
targets = {}
for index, offset, address, size in sections[:]:
    if index >= 7:
        continue
    for displacement in range(0, size, 4):
        pc = address + displacement
        opcode = struct.unpack_from('>I', original, offset + displacement)[0]
        primary = opcode >> 26
        if primary not in (16, 18):
            continue
        width = 16 if primary == 16 else 26
        immediate = opcode & ((1 << width) - 4)
        if immediate & (1 << (width - 1)):
            immediate -= 1 << width
        target = (immediate if opcode & 2 else pc + immediate) & 0xffffffff
        targets.setdefault(target, []).append({'address': hex(pc), 'opcode': hex(opcode), 'link': bool(opcode & 1)})

decoder = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
decoder.skipdata = True
records = []
for address in missing:
    index, offset, start, size = next(section for section in sections if section[2] <= address < section[2] + section[3])
    lower, upper = max(start, address - 128), min(start + size, address + 132)
    window = original[offset + lower - start:offset + upper - start]
    instructions = [{'address': hex(item.address), 'bytes': item.bytes.hex(),
                     'mnemonic': item.mnemonic, 'operands': item.op_str} for item in decoder.disasm(window, lower)]
    nearby_entries = sorted(catalogue, key=lambda row: abs(row[0] - address))[:4]
    records.append({'address': hex(address), 'sectionIndex': index, 'window': instructions,
                    'containingCatalogueRanges': [[hex(value) for value in row] for row in catalogue if row[1] <= address < row[2]],
                    'nearestEntries': [[hex(value) for value in row] for row in nearby_entries],
                    'directTargetsInWindow': {hex(target): refs for target, refs in targets.items() if lower <= target < upper}})
report = {'result': 'FRSP_MISSING_TEXT_CANDIDATES_STATIC_INSPECTION', 'records': records,
          'originalSha256': sha(original_path), 'moduleAuditSha256': sha(private / 'mass-frsp/audit.json'),
          'catalogueSha256': sha(catalogue_path), 'scriptSha256': sha(Path(__file__)),
          'limits': ['Raw text decode and direct branch candidates; indirect reachability and function ownership not proven.',
                     'Neighbouring valid instruction decodes do not by themselves establish executable code.',
                     'No original/generated module changes, no function insertion and no runtime activation.']}
(private / 'mass-frsp/missing-address-analysis.json').write_text(json.dumps(report, indent=2) + '\n')
for record in records:
    print(record['address'], 'ranges', record['containingCatalogueRanges'])
    for instruction in record['window']:
        print(instruction['address'], instruction['bytes'], instruction['mnemonic'], instruction['operands'])
    print('DIRECT REFERENCES', record['directTargetsInWindow'])
