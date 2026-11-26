"""Reuse whole original protection oracle with the measured IOS58 usable MEM2 end."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_memory_protection_dolphin.py')
body = parent.read_text().replace('dolphin-memory-protection', 'dolphin-memory936')
assert body.count('0x93400000') == 1
body = body.replace('0x93400000', '0x93600000').replace('93400000usable end', '93600000usable end')
body = body.replace('run_memory_protection_dolphin.ps1', 'run_memory936_dolphin.ps1')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-memory936/generation.json')
report = json.loads(path.read_text())
report['profileGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['loaderProofSha256'] = hashlib.sha256(Path('work/private-game/static-recomp/dolphin-loader-snapshot/comparison.json').read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
