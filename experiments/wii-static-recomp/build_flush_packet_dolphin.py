"""Run the existing original EE flush cases at the observed IPC MEM2 line."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_flush_ee_dolphin.py')
body = parent.read_text().replace('dolphin-flush-ee', 'dolphin-flush-packet')
body = body.replace('run_flush_ee_dolphin.ps1', 'run_flush_packet_dolphin.ps1')
marker = 'body = parent.read_text()'
assert body.count(marker) == 1
body = body.replace(marker, marker + ".replace('0x80550000', '0x935e0020').replace('0xc0550000', '0xd35e0020')")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-flush-packet/generation.json')
report = json.loads(path.read_text())
report['packetParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'].append('Observed IPC MEM2 range with laboratory dirty patterns; no IOS request or original caller execution.')
path.write_text(json.dumps(report, indent=2) + '\n')
