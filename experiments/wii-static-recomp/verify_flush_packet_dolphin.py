"""Check original CPU flush/physical visibility at the observed IPC MEM2 range."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_flush_ee_dolphin.py')
body = parent.read_text().replace('dolphin-flush-ee', 'dolphin-flush-packet')
body = body.replace('build_flush_ee_dolphin.py', 'build_flush_packet_dolphin.py')
body = body.replace('run_flush_ee_dolphin.ps1', 'run_flush_packet_dolphin.ps1')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-flush-packet/comparison.json')
generation = json.loads((path.parent / 'generation.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert generation['packetParentSha256'] == sha(Path('experiments/wii-static-recomp/build_flush_ee_dolphin.py'))
assert [row['address'] for row in generation['records']] == [0x935e0020] * 8 + [0x935e0027] * 8
report = json.loads(path.read_text())
report['result'] = 'ORIGINAL_MEM2_IPC_LINE_DCFLUSH16_CPU_SC_RFI_VISIBILITY_PASS'
report['packetVerifierParentSha256'] = sha(parent)
path.write_text(json.dumps(report, indent=2) + '\n')
