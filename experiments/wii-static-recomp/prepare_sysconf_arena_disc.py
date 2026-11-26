"""Stage arena diagnostics in their own private fixture."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_sysconf_register_disc.py')
body = parent.read_text().replace('dolphin-sysconf-register', 'dolphin-sysconf-arena').replace(
    'run_sysconf_register_disc_dolphin.ps1', 'run_sysconf_arena_disc_dolphin.ps1')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-sysconf-arena-disc/preparation.json')
report = json.loads(path.read_text())
report['arenaParentPreparerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
