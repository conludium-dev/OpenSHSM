"""Keep cache oracle disc/profile separate from the successful burst controls."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_di_burst_events_disc.py')
body = parent.read_text().replace('dolphin-di-burst-events', 'dolphin-di-cache-events')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-di-cache-events-disc/preparation.json')
report = json.loads(path.read_text())
report['cacheParentPreparerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
