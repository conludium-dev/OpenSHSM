"""Reuse existing dtk SDK labels and pin original bytes before sender integration."""
from pathlib import Path
import hashlib
import json
import re
import struct

private = Path('work/private-game/static-recomp')
output = private / 'ipc-sdk-roots'
output.mkdir(exist_ok=True)
assembly_path = private / 'dtk-output/asm/auto_03_802045CC_text.s'
assembly = assembly_path.read_text()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
selected = ['IPCInit', 'IPCReadReg', 'IPCWriteReg', 'IPCGetBufferHi', 'IPCGetBufferLo', 'IPCSetBufferLo',
            'IPCInterruptHandler', 'IPCCltInit', 'IOS_OpenAsync', 'IOS_Open']
records = []
for name in selected:
    pattern = rf'# \.text:0x([0-9A-Fa-f]+) \| 0x([0-9A-Fa-f]+) \| size: 0x([0-9A-Fa-f]+)\n\.fn {name}, (?:global|local)\n(.*?)\.endfn {name}'
    match = re.search(pattern, assembly, re.S)
    assert match, name
    relative, address, size = (int(value, 16) for value in match.groups()[:3])
    instructions = re.findall(r'/\* ([0-9A-F]{8}) [0-9A-F]{8}  ([0-9A-F ]+) \*/\s*(.*)', match.group(4))
    assert len(instructions) * 4 == size, name
    for index, (pc, hexadecimal, disassembly) in enumerate(instructions):
        pc = int(pc, 16)
        assert pc == address + index * 4
        section = next(i for i in range(7) if header[18 + i] <= pc < header[18 + i] + header[36 + i])
        offset = header[section] + pc - header[18 + section]
        assert bytes.fromhex(hexadecimal) == dol[offset:offset + 4]
    records.append({'name': name, 'address': hex(address), 'size': size, 'objectRelativeOffset': hex(relative),
                    'instructionCount': len(instructions), 'originalByteSha256': hashlib.sha256(b''.join(bytes.fromhex(row[1]) for row in instructions)).hexdigest()})
assert {row['name']: row['address'] for row in records}['IOS_Open'] == '0x80242550'
assert {row['name']: row['address'] for row in records}['IPCWriteReg'] == '0x80241c30'
report = {'result': 'TEN_EXISTING_DTK_SDK_ROOTS_ORIGINAL_DOL_BYTES_MATCH', 'records': records,
          'assemblySha256': sha(assembly_path), 'objectSha256': sha(private / 'dtk-output/obj/auto_03_802045CC_text.o'),
          'dolSha256': sha(dol_path), 'scriptSha256': sha(Path(__file__)),
          'limits': ['SDK names inherited from dtk analysis/signatures, not original retained debug symbols.',
                     'Static byte/boundary check; runtime ABI, sender execution, allocator/cache/interrupt behavior unverified.']}
(output / 'analysis.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS10existingSDKroots/DOLbytes; IPCReadReg80241C20/IPCWriteReg80241C30/IOS_Open80242550; runtime pending')
