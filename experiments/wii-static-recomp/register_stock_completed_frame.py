"""Register verified private experiment manifests, without changing any default."""
from pathlib import Path
import argparse
import hashlib
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
args = parser.parse_args()
path = args.build.resolve()
sha = lambda item: hashlib.sha256(Path(item).read_bytes()).hexdigest()
build = json.loads(path.read_text())
component_path = path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'COMPLETED_FRAME_GL172_EVICTION1600_GPU16_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'
assert component['buildSha256'] == sha(path)
exe = Path(build['executablePath']).resolve()
assert exe.name == 'OpenSHSMStockCompletedFrame' and exe.parent == path.parent
assert exe.parent.parent == Path('/private/tmp')
assert re.fullmatch(r'openshsm-completed-frame-[A-Za-z0-9_-]+', exe.parent.name)
assert sha(exe) == build['executableSha256']
assert sha(build['archivePath']) == build['archiveSha256']
for file, digest in {**build['dependencies'], **build['retainedInputs'], **component['reusedVerifierSha256']}.items():
    assert sha(file) == digest
assert sha(component['gpuProofPath']) == component['gpuProofSha256']
for filename, key in [('gl-verification.json', 'glProofSha256'),
    ('timer-latch-verification.json', 'timerProofSha256')]:
    assert sha(path.parent / filename) == component[key]
output = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline/window-completed-frame'
output.mkdir(exist_ok=True)
for original in [path, component_path]:
    target = output / original.name
    assert not target.exists() or target.read_bytes() == original.read_bytes(), 'Refuse to replace an existing registration'
    if not target.exists():
        target.write_bytes(original.read_bytes())
print('COMPLETED_FRAME_PRIVATE_MANIFESTS_REGISTERED_NOT_DEFAULT', output)
