"""Rebuild the existing SI vector proof in isolation with first-use FPU disabled."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parents = []
for name in ('build_si_vector_native.py', 'verify_si_vector_native.py'):
    parent = experiment / name
    body = parent.read_text().replace('si-vector-native', 'fpu-si-vector-regression')
    exec(compile(body, str(parent), 'exec'), {'__file__': str(parent)})
    parents.append({'path': str(parent), 'sha256': hashlib.sha256(parent.read_bytes()).hexdigest()})
output = Path('work/private-game/static-recomp/fpu-si-vector-regression')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'regressions.json').write_text(json.dumps({'result': 'FPU_DISABLED_EXISTING_SI_VECTOR16_AND_NEGATIVES_PASS',
    'runnerSha256': sha(Path(__file__)), 'parents': parents, 'comparisonSha256': sha(output / 'comparison.json'),
    'limits': ['Isolated output preserves retained boot object hashes; FPU first-use remains disabled in the SI profile.',
        'Existing SI packet/context/negative scope only; no full boot/physical Wii acceptance.']}, indent=2) + '\n')
print('PASS first-use FPU extension preserves existing SI vector16/context return and negative gates')
