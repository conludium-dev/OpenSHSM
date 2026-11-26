"""Stage the whole-SC oracle separately using the existing own-disc preparation."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_es_close_disc.py')
body = parent.read_text().replace('dolphin-es-close', 'dolphin-sysconf').replace(
    'run_es_close_disc_dolphin.ps1', 'run_sysconf_disc_dolphin.ps1').replace(
    'verify_es_datadir_disc.py', 'verify_es_close_disc.py')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-sysconf-disc/preparation.json')
report = json.loads(path.read_text())
report['sysconfParentPreparerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
