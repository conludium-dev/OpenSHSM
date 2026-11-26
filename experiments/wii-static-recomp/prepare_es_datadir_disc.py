"""Stage GetDataDir in a separate own-disc lab using the existing private preparation."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_es_disc_oracle.py')
body = parent.read_text().replace('dolphin-es-disc', 'dolphin-es-datadir-disc').replace(
    'dolphin-es-title', 'dolphin-es-datadir').replace('verify_es_title_dolphin.py', 'verify_es_disc_oracle.py').replace(
    'run_es_disc_dolphin.ps1', 'run_es_datadir_disc_dolphin.ps1')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-es-datadir-disc/preparation.json')
report = json.loads(path.read_text())
report['parentPreparerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
