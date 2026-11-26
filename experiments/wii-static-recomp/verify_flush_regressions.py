"""Rebuild the existing first-use FPU proof with the flush profile disabled."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parents = []
for name in ('build_fpu_first_use_native.py', 'verify_fpu_first_use_native.py'):
    parent = experiment / name
    body = parent.read_text().replace('fpu-first-use-native', 'flush-fpu-regression')
    exec(compile(body, str(parent), 'exec'), {'__file__': str(parent)})
    parents.append({'path': str(parent), 'sha256': hashlib.sha256(parent.read_bytes()).hexdigest()})
output = Path('work/private-game/static-recomp/flush-fpu-regression')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'regressions.json').write_text(json.dumps({'result': 'FLUSH_DISABLED_FPU16_AND10_GUARDS_REGRESSION_PASS',
    'runnerSha256': sha(Path(__file__)), 'parents': parents, 'comparisonSha256': sha(output / 'comparison.json'),
    'limits': ['Isolated output preserves boot objects; default flush profile disabled.', 'Existing first-use FPU scope only, not full boot.']}, indent=2) + '\n')
print('PASS flush extension preserves existing original FPU vector/retry16 and10guards')
