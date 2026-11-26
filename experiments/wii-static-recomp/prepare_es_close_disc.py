"""Reuse the validated own-disc preparation for a separate original close fixture."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_es_datadir_disc.py')
body = parent.read_text().replace('dolphin-es-datadir', 'dolphin-es-close').replace(
    'run_es_datadir_disc_dolphin.ps1', 'run_es_close_disc_dolphin.ps1').replace(
    'verify_es_disc_oracle.py', 'verify_es_datadir_disc.py')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-es-close-disc/preparation.json')
report = json.loads(path.read_text())
report['closeParentPreparerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
