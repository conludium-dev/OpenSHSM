"""Call whole original DiGetTicketView after the verified own-disc DVD/ES chain."""
from pathlib import Path
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/build_di_burst_dolphin.py')
body = parent.read_text().replace('dolphin-di-burst', 'dolphin-es-di-ticket')
marker = 'code.extend([dform(32, 0, 1, 20), spr(0, 8, True), dform(14, 1, 1, 16), 0x4e800020])'
assert body.count(marker) == 1
extra = '''code.append(dform(36, 3, 1, 8))
code.append(dform(14, 3, 0, 0))
pointer(code, 4, 0x806f4000)
ticket_call = text + len(code) * 4
code.append(branch(ticket_call, 0x80249a00, True))
pointer(code, 12, 0x806f4200)
code.extend([dform(36, 3, 12, 0), 0x7c0000a6, dform(36, 0, 12, 4)])
pointer(code, 3, 0x806f4000)
code.append(dform(14, 4, 0, 216))
code.append(branch(text + len(code) * 4, 0x80212fd0, True))
pointer(code, 3, 0x806f4200)
code.append(dform(14, 4, 0, 8))
code.append(branch(text + len(code) * 4, 0x80212fd0, True))
code.append(dform(32, 3, 1, 8))
'''
body = body.replace(marker, extra + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-es-di-ticket')
image = bytearray((output / 'fpr-init.dol').read_bytes())
layout = list(struct.unpack('>64I', image[:256]))
address, size = 0x806f4000, 0x240
assert all(not layout[36 + i] or address >= layout[18 + i] + layout[36 + i] or address + size <= layout[18 + i] for i in range(18))
assert not layout[55] or address >= layout[54] + layout[55] or address + size <= layout[54]
slot = next(i for i in range(7, 18) if not layout[36 + i])
layout[slot], layout[18 + slot], layout[36 + slot] = len(image), address, size
image.extend(bytes(size))
image[:256] = struct.pack('>64I', *layout)
(output / 'fpr-init.dol').write_bytes(image)
path = output / 'generation.json'
report = json.loads(path.read_text())
report.update(harnessSha256=hashlib.sha256(image).hexdigest(),
    wrapperSha256=hashlib.sha256(Path('experiments/wii-static-recomp/run_es_di_ticket_disc_dolphin.ps1').read_bytes()).hexdigest(),
    ticketParentGeneratorSha256=hashlib.sha256(parent.read_bytes()).hexdigest(),
    ticketOracle={'target': 0x80249a00, 'optionalInput': 0, 'output': address, 'length': 216,
        'scalars': 0x806f4200, 'sectionSlot': slot, 'sectionBytes': size})
report['limits'] = ['Whole original DVD/ES chain then whole original ESP_DiGetTicketView(NULL,private216-byte LAB output).',
    'Original SDK creates vectors and calls IOS; no ticket payload/result/FD synthesized. Existing ES result preserved across extra call.',
    'Separate private LAB output block not a game asset/runtime requirement; actual service response remains to be measured.']
path.write_text(json.dumps(report, indent=2) + '\n')
