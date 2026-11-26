"""Prepare a separate private COW disc/profile for original DI observations."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_di_initialized_disc.py')
body = parent.read_text().replace('dolphin-di-initialized', 'dolphin-di-events')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-di-events-disc/preparation.json')
report = json.loads(path.read_text())
report['eventsParentPreparerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
