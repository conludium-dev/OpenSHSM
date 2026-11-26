"""Register the verified four-call diagnostic delta for bounded live acceptance."""
from pathlib import Path
import argparse
import hashlib
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
args = parser.parse_args()
path = args.build.resolve()
build = json.loads(path.read_text())
component_path = path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert component['buildSha256'] == sha(path)
assert component['result'] == 'CONTEXT_STAGE_CACHE234_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'
for file, digest in {**build['dependencies'], **build['retainedInputs'], **component['reusedVerifierSha256']}.items():
    assert sha(file) == digest
assert sha(component['cacheProofPath']) == component['cacheProofSha256']
assert sha(path.parent / 'timer-latch-verification.json') == component['timerProofSha256']
source = Path(build['originalSourcePath']).read_text()
for before, after in build['sourcePatches']:
    assert source.count(before) == 1 and after == ''
    source = source.replace(before, after, 1)
assert source == Path(build['sourcePath']).read_text()
assert sha(build['objectPath']) == build['objectSha256']
assert sha(build['archivePath']) == build['archiveSha256']
exe = Path(build['executablePath']).resolve()
assert exe.parent == path.parent and exe.parent.parent == Path('/private/tmp')
assert exe.name == 'OpenSHSMStockContextStageGate'
assert re.fullmatch(r'openshsm-context-stage-gate-[A-Za-z0-9_-]+', exe.parent.name)
assert sha(exe) == build['executableSha256']
output = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline/window-context-stage'
output.mkdir(exist_ok=True)
for original in [path, component_path]:
    target = output / original.name
    assert not target.exists() or target.read_bytes() == original.read_bytes()
    if not target.exists():
        target.write_bytes(original.read_bytes())
print('CONTEXT_STAGE_REGISTERED_FOR_LIVE_NOT_DEFAULT', output)
