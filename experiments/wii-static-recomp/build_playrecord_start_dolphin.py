"""Execute whole original play-record start after the verified own-disc close chain."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_es_close_after_consumption_dolphin.py')
body = parent.read_text().replace('dolphin-es-close-after-consumption','dolphin-playrecord-start').replace(
    'run_es_close_after_consumption_disc_dolphin.ps1','run_playrecord_start_disc_dolphin.ps1')
marker = 'body = body.replace(ast.get_source_segment(body, node.value), repr(extra))'
assert body.count(marker) == 1
extra = '''code.append(branch(text + len(code) * 4, 0x8021d2a0, True))
pointer(code, 12, 0x806f4280)
code.extend([dform(36, 3, 12, 0), 0x7c0000a6, dform(36, 0, 12, 4)])
for slot, address in [(8,0x80528a40),(12,0x8052ab40),(16,0x8052ab44),(20,0x8052ab48),
    (24,0x8052ab4c),(28,0x8052ab50),(32,0x8052ab54),(36,0x804931d0),(40,0x8052aff8)]:
    pointer(code, 11, address)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 12, slot)])
pointer(code, 3, 0x806f4280)
code.append(dform(14, 4, 0, 64))
code.append(branch(text + len(code) * 4, 0x80212fd0, True))
'''
body = body.replace(marker, 'extra += '+repr(extra)+'\n'+marker+"\nbody = body.replace('0x280', '0x380')")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
path = Path('work/private-game/static-recomp/dolphin-playrecord-start/generation.json')
report = json.loads(path.read_text())
report['playrecordParentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['playrecordOracle'] = {'target':0x8021d2a0,'startScalars':0x806f4280,'scalarBytes':64,
    'buffer':0x80493120,'bufferBytes':128,'fileInfo':0x804931d0}
report['limits'] = ['Whole original __OSStartPlayRecord after original DVD/ES/ticket/ES16/close; original SDK owns callbacks/requests.',
    'Void function return register is captured only as opaque state, not an API status contract.',
    'Separate LAB profile may update its system-menu bookkeeping; no original assets/source LAB captures modified.',
    'Dynamic completion/order and buffer-read identity require live capture and callback trace.']
path.write_text(json.dumps(report,indent=2)+'\n')
