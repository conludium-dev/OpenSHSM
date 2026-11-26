"""Stage whole SC chain separately from failed arena diagnostics."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_sysconf_disc.py')
body = parent.read_text().replace('dolphin-sysconf', 'dolphin-sysconf-chain').replace(
    'run_sysconf_disc_dolphin.ps1', 'run_sysconf_chain_disc_dolphin.ps1')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-sysconf-chain-disc/preparation.json')
report = json.loads(path.read_text())
report['chainParentPreparerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
