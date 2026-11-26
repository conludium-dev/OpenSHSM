"""Register a parser-only candidate after native and real GPU checks, not as default."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--native-proof', type=Path, required=True)
parser.add_argument('--shader-proof', type=Path, required=True)
parser.add_argument('--pipeline-proof', type=Path, required=True)
args = parser.parse_args()
path = args.build.resolve()
assert path.parent.parent == Path('/private/tmp') and path.parent.name.startswith('openshsm-bp-parse-order-')
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
build = json.loads(path.read_text())
assert build['result'] == 'BP_PARSE_ORDER_BUILT_UNVERIFIED'
for file, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(file) == digest
source = Path(build['sourcePath']).read_text()
for before, after in reversed(build['patches']):
    assert source.count(after) == 1
    source = source.replace(after, before, 1)
assert source == Path(build['originalSourcePath']).read_text()
assert sha(build['objectPath']) == build['objectSha256']
assert sha(build['archivePath']) == build['archiveSha256']
parent_path = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline/window-context-stage/build.json'
parent = json.loads(parent_path.read_text())
assert build['parentBuildSha256'] == sha(parent_path)
for member, digest in build['members'].items():
    actual = subprocess.check_output(['/usr/bin/ar', '-p', build['archivePath'], member])
    old = subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], member])
    assert hashlib.sha256(actual).hexdigest() == digest
    assert member == 'fifo_parser.cpp.o' or actual == old
proofs = {}
for role, proof_path, expected in [
    ('native', args.native_proof, 'BP_PARSE_ORDER_ACTUAL_NATIVE_DIRECT_MASK_SPLIT_DL_KONST_PASS'),
    ('shader', args.shader_proof, 'BP_PARSE_ORDER_REAL_GPU_BASELINE_LEAK_CANDIDATE_ORDERED_PASS'),
    ('pipeline', args.pipeline_proof, 'BP_ORDER_ACTUAL_FIFO_PE6_COPY4_PRESENT6_POST_ORDER6_PASS')]:
    proof_path = proof_path.resolve()
    assert proof_path.parent.parent == Path('/private/tmp')
    proof = json.loads(proof_path.read_text())
    assert proof['result'] == expected and proof['buildSha256'] == sha(path)
    for file, digest in proof['dependencies'].items():
        assert sha(file) == digest
    proofs[role] = {'path': str(proof_path), 'sha256': sha(proof_path)}
exe = Path(build['executablePath']).resolve()
assert exe.parent == path.parent and exe.name == 'OpenSHSMStockBPParseOrder'
assert sha(exe) == build['executableSha256']
component = {'result': 'BP_ORDER_NATIVE_SHADER_GPU_PIPELINE_RETAINED_PARENT_VERIFIED',
    'buildSha256': sha(path), 'proofs': proofs, 'registrationScriptSha256': sha(Path(__file__)),
    'limits': ['Parser and actual GPU component checks; full game/menu/audio/performance acceptance pending.',
        'All non-parser runtime and guest inputs retained, their previous narrow checks inherited, not rerun.',
        'Registered for bounded live acceptance only; not default or public release.']}
component_path = path.parent / 'component-verification.json'
component_path.write_text(json.dumps(component, indent=2) + '\n')
output = parent_path.parent.parent / 'window-bp-order'
output.mkdir(exist_ok=True)
for original in [path, component_path]:
    target = output / original.name
    assert not target.exists() or target.read_bytes() == original.read_bytes()
    if not target.exists():
        target.write_bytes(original.read_bytes())
print('BP_ORDER_REGISTERED_FOR_BOUNDED_LIVE_NOT_DEFAULT', output)
