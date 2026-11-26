"""Stage DI startup independently using same validated own-disc/profile COW preparation."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_sysconf_product_oracle.py')
body = parent.read_text().replace('dolphin-sysconf-product-oracle-disc', 'dolphin-di-open-disc')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/dolphin-di-open-disc')
generated = Path('work/private-game/static-recomp/dolphin-di-open/fpr-init.dol')
(output / 'DATA/sys/main.dol').write_bytes(generated.read_bytes())
path = output / 'preparation.json'
report = json.loads(path.read_text())
report['harnessSha256'] = hashlib.sha256(generated.read_bytes()).hexdigest()
report['parentPreparerSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
