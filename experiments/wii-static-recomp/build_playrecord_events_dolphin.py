"""Reuse replay observers for the whole original play-record callback lifetime."""
from pathlib import Path
import ast
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/build_sysconf_events_dolphin.py')
body = parent.read_text()
body = body.replace('verify_sysconf_chain.py', 'verify_playrecord_start_dolphin.py')
body = body.replace('dolphin-sysconf-long', 'dolphin-playrecord-start')
body = body.replace('dolphin-sysconf-events-fixed', 'dolphin-playrecord-events')
body = body.replace('run_sysconf_events_fixed_disc_dolphin.ps1', 'run_playrecord_events_disc_dolphin.ps1')
body = body.replace('0x806c0000, 0x806e0000', '0x806d4000, 0x80740000')
sites = [(1, 0x80241c30, 0x5460103a, 'IPCWriteReg_entry'),
    (2, 0x8021cde0, 0x9421ffe0, 'PlayRecord_callback_entry'),
    (3, 0x80240680, 0x9421fff0, 'ISFS_callback_entry'),
    (4, 0x80244e30, 0x9421fff0, 'NAND_open_callback_entry'),
    (5, 0x802407d0, 0x2c1f0000, 'ISFS_after_higher_callback'),
    (6, 0x802438b0, 0x9421ffe0, 'iosFree_entry'),
    (7, 0x80241e9c, 0x806da454, 'IPC_before_packet_free')]
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == 'sites' for target in node.targets))
body = body.replace(ast.get_source_segment(body, node.value), repr(sites))
old = '(640, 0x804b3000, 400), (1040, 0x935e1000, 64), (1104, 0x935e0000, 64)'
regions = [(640, 0x80493120, 128), (768, 0x804931d0, 140),
    (912, 0x8049325c, 144), (1056, 0x80528a40, 4), (1060, 0x8052ab40, 32),
    (1104, 0x804b2a80, 80), (1184, 0x80492658, 64), (1248, 0x80492260, 32)]
assert body.count(old) == 1
body = body.replace(old, ', '.join(repr(region) for region in regions))
body = body.replace('Nine private', 'Seven private').replace('nine replay sites', 'seven replay sites')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-playrecord-events')
image = (output / 'fpr-init.dol').read_bytes()
layout = struct.unpack('>64I', image[:256])
spans = [(layout[18 + i], layout[18 + i] + layout[36 + i]) for i in range(18) if layout[36 + i]]
if layout[57]:
    spans.append((layout[56], layout[56] + layout[57]))
for index, (start, end) in enumerate(spans):
    assert 0x80000000 <= start < end <= 0x81800000
    for other_start, other_end in spans[index + 1:]:
        assert end <= other_start or other_end <= start, 'Observer overlaps an existing section/BSS'
path = output / 'generation.json'
report = json.loads(path.read_text())
report['replayParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['playrecordEventRegions'] = regions
report['limits'].append('This is an observation fixture, not a callback result or native FS implementation. Live endpoint/order comparison remains required.')
path.write_text(json.dumps(report, indent=2) + '\n')
