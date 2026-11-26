"""Verify original DEC programming and the subsequent genuine callback/free chain."""
from pathlib import Path
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_playrecord_events_dolphin.py')
body = parent.read_text().replace('dolphin-playrecord-events','dolphin-playrecord-dec-events').replace(
    'verify_playrecord_events_fixture.py','verify_playrecord_dec_fixture.py').replace(
    'prepare_playrecord_events_disc.py','prepare_playrecord_dec_events_disc.py')
body = body.replace('(189, 0)','(191, 0)').replace('{1:121, 2:4, 3:9, 4:3, 5:9, 6:32, 7:11}',
    '{1:121, 2:4, 3:9, 4:3, 5:9, 6:32, 7:11, 8:1, 9:1}')
body = body.replace('    checks.append((index, offset, payload))',
    '    checks.append((index + (2 if index >= 184 else 0), offset, payload))')
marker = 'check(events)\nlocations ='
assert body.count(marker) == 1
extra = '''for index,kind in ((184,8),(185,9)):
    checks.append((index,0,struct.pack('>2I',kind,patches[kind]['address'])))
    checks.append((index,12,struct.pack('>2I',0x80212078,0x32)))
    checks.append((index,24,struct.pack('>I',0x7fffffff)))
    checks.append((index,1056,struct.pack('>I',4)))
checks.append((184,60,struct.pack('>I',0xffffffff)))
checks.append((185,60,struct.pack('>I',0x7ffffffe)))
'''
body = body.replace(marker,extra + marker)
body = body.replace('for first, second in swaps:',
    'swaps = [(first + (2 if first >= 184 else 0), second + (2 if second >= 184 else 0)) for first, second in swaps]\n'
    'swaps += [(183,184),(184,185),(185,186)]\nfor first, second in swaps:')
body = body.replace("'eventCount':count,", "'eventCount':count, 'decParentSha256':sha(experiment / 'build_playrecord_events_dolphin.py'),")
body = body.replace('PASS189 original events','PASS191 original events/DEC beforeFFFFFFFF-written7FFFFFFF-after7FFFFFFE')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
capture = json.loads(Path('work/private-game/static-recomp/dolphin-playrecord-dec-events-disc/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
import base64
raw = base64.b64decode(capture['events'])
countdown = [struct.unpack_from('>I',raw,64 + index * 1280 + 60)[0] for index in range(185,191)]
assert all(0 < right < left < 0x80000000 for left,right in zip(countdown,countdown[1:]))
path = Path('work/private-game/static-recomp/dolphin-playrecord-dec-events-disc/playrecord-events-comparison.json')
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_DEC_WRITE7FFFFFFF_COUNTDOWN_AND_CALLBACK_RETIREMENT_PASS'
report['dec'] = {'beforeIndex':184,'afterIndex':185,'written':0x7fffffff,'before':0xffffffff,'after':0x7ffffffe,
    'callbackReturnedIndex':186,'workFreeIndex':187,'packetFreeIndex':189,'finalIndex':190,'countdown':countdown}
report['limits'].append('Two added DEC replay sites; post-write countdown measured only in this LAB interval, not negative-write/underflow IRQ/reprogramming/physical Wii or native DEC support.')
path.write_text(json.dumps(report,indent=2) + '\n')
