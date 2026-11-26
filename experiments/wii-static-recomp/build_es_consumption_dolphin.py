"""Call the whole original ES16 wrapper using the original ticket-view ticket ID."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_es_di_ticket_dolphin.py')
body = parent.read_text().replace('dolphin-es-di-ticket', 'dolphin-es-consumption').replace(
    'run_es_di_ticket_disc_dolphin.ps1', 'run_es_consumption_disc_dolphin.ps1')
marker = 'code.append(dform(32, 3, 1, 8))'
assert body.count(marker) == 1
extra = '''pointer(code, 12, 0x806f4220)
pointer(code, 0, 0x12345678)
code.append(dform(36, 0, 12, 0))
pointer(code, 12, 0x806f4000)
code.extend([dform(32, 3, 12, 4), dform(32, 4, 12, 8), dform(14, 5, 0, 0)])
pointer(code, 6, 0x806f4220)
code.append(branch(text + len(code) * 4, 0x80249ce0, True))
pointer(code, 12, 0x806f4240)
code.extend([dform(36, 3, 12, 0), 0x7c0000a6, dform(36, 0, 12, 4)])
for capture_address in (0x806f4220, 0x806f4240):
    pointer(code, 3, capture_address)
    code.append(dform(14, 4, 0, 32))
    code.append(branch(text + len(code) * 4, 0x80212fd0, True))
'''
body = body.replace(marker, extra + marker).replace('address, size = 0x806f4000, 0x240', 'address, size = 0x806f4000, 0x280')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-es-consumption/generation.json')
report = json.loads(path.read_text())
report['consumptionParentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['consumptionOracle'] = {'target': 0x80249ce0, 'ticketIdSource': 0x806f4004,
    'optionalArray': 0, 'count': 0x806f4220, 'initialCount': 0x12345678, 'scalars': 0x806f4240}
report['limits'] = ['Whole original DVD/ES/ticket chain followed by original ES16 wrapper with captured ticket ID and NULL array.',
    'Private count sentinel proves an output write, not an IOS reply synthesized by the harness.',
    'Original SDK creates requests/vectors; return/count/control preservation still require a live original capture.',
    'Dolphin LAB is not physical IOS/drive/cache timing proof; original SDK/game bytes unchanged.']
path.write_text(json.dumps(report, indent=2) + '\n')
