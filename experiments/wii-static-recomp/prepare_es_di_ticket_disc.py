"""Separate COW copy/profile for original ticket-view oracle."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/prepare_di_initialized_disc.py')
body = parent.read_text().replace('dolphin-di-initialized', 'dolphin-es-di-ticket')
output = Path('work/private-game/static-recomp/dolphin-es-di-ticket-disc')
if not (output / 'preparation.json').exists():
    exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
else:
    generated = Path('work/private-game/static-recomp/dolphin-es-di-ticket/fpr-init.dol')
    capture_path = output / 'fpr-init-true-dolphin.json'
    if capture_path.exists():
        capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
        digest = hashlib.sha256(generated.read_bytes()).hexdigest()
        assert capture['harnessSha256'].lower() == digest == hashlib.sha256((output / 'DATA/sys/main.dol').read_bytes()).hexdigest(), 'Refusing to replace a captured oracle with a different harness'
    (output / 'DATA/sys/main.dol').write_bytes(generated.read_bytes())
    path = output / 'preparation.json'
    report = json.loads(path.read_text())
    report['preparerSha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['harnessSha256'] = hashlib.sha256(generated.read_bytes()).hexdigest()
    path.write_text(json.dumps(report, indent=2) + '\n')
