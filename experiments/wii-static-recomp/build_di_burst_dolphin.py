"""Whole DVDInit and DVDInquiryAsync own all state, followed by synchronous ESP_InitLib."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_di86_dolphin.py')
body = parent.read_text().replace("output = root / 'dolphin-di86'", "output = root / 'dolphin-di-burst'")
marker = 'index = calls[1]'
assert body.count(marker) == 1
body = body.replace(marker, '''first_site = 0x80600000 + calls[0] * 4
first_offset = layout[main] + calls[0] * 4
struct.pack_into('>I', image, first_offset, branch(first_site, 0x8021f9d0, True))
''' + marker)
start, end = body.index('code = [dform(37,'), body.index('resume = text + len(code) * 4')
code = '''code = [dform(37, 1, 1, -16), spr(0, 8), dform(36, 0, 1, 20)]
pointer(code, 0, 0x2032)
code.append(0x7c000124)
pointer(code, 3, 0x80492280)
pointer(code, 4, 0x80492260)
pointer(code, 5, 0x80211060)
call = text + len(code) * 4
code.append(branch(call, 0x80223a50, True))
code.extend([dform(36, 3, 30, 408), 0x7c0000a6, dform(36, 0, 30, 412)])
es_call = text + len(code) * 4
code.append(branch(es_call, 0x80249790, True))
code.extend([dform(32, 0, 1, 20), spr(0, 8, True), dform(14, 1, 1, 16), 0x4e800020])
'''
body = body[:start] + code + body[end:]
body = body.replace("'target': 0x80227dd0", "'target': 0x80223a50")
body = body.replace("generation['records'][7]['kind'] = 'DI86_async'", "generation['records'][6]['kind'] = 'DVDInit'\ngeneration['records'][7]['kind'] = 'DVDInquiryAsync_then_ESP_InitLib'\ngeneration['burst'] = {'firstSite': first_site, 'firstOffset': first_offset, 'DVDInit': 0x8021f9d0, 'inquiryCall': call, 'inquiry': 0x80223a50, 'block': 0x80492280, 'output': 0x80492260, 'completion': 0x80211060, 'upperCallback': 0x80222f80, 'esCall': es_call, 'es': 0x80249790}")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-di-burst/generation.json')
report = json.loads(path.read_text())
report['burstParentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['nativeBurstInputsSha256'] = hashlib.sha256(Path('work/private-game/static-recomp/mass-di86-idle-observer/observation.json').read_bytes()).hexdigest()
report['limits'] = ['Whole original DVDInit initializes queues, then whole DVDInquiryAsync creates block, low86/12 and both callbacks; ES opens synchronously.',
    'Caller MSR2032 and measured block/output/completion addresses are laboratory inputs; Inquiry API408/412 before ES call, no forced state/FD/response/callback.',
    'Original SDK CPU experiment, not complete native burst/physical drive/cycles; original inquiry payload must be captured and verified.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('Prepared whole DVDInit→DVDInquiryAsync→ESP_InitLib; SDK owns command block and callback chain')
