"""Register only the bounded observer with checked GPU evidence, never as default."""
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
assert component['result'] == 'PE_CADENCE_GPU16_SETTINGS3_RETAINED_PARENT_COMPONENTS_VERIFIED'
assert component['buildSha256'] == sha(path)
exe = Path(build['executablePath']).resolve()
assert exe.name == 'OpenSHSMStockPECadence' and exe.parent == path.parent
assert exe.parent.parent == Path('/private/tmp')
assert re.fullmatch(r'openshsm-pe-cadence-[A-Za-z0-9_-]+', exe.parent.name)
assert sha(exe) == build['executableSha256']
assert sha(build['archivePath']) == build['archiveSha256']
for file, digest in {**build['dependencies'], **build['retainedInputs'], **component['dependencies']}.items():
    assert sha(file) == digest
for row in component['records']:
    assert sha(row['proofPath']) == row['proofSha256']
output = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline/window-pe-cadence'
output.mkdir(exist_ok=True)
for original in [path, component_path]:
    target = output / original.name
    assert not target.exists() or target.read_bytes() == original.read_bytes()
    if not target.exists():
        target.write_bytes(original.read_bytes())
print('PE_CADENCE_REGISTERED_NOT_DEFAULT', output)
