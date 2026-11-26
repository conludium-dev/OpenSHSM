"""Private COW staging for whole original DVD inquiry/ES burst."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_di_initialized_disc.py')
body = parent.read_text().replace('dolphin-di-initialized', 'dolphin-di-burst')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-di-burst-disc/preparation.json')
report = json.loads(path.read_text())
report['burstParentPreparerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
