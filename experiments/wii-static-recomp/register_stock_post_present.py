"""Verify main-only link delta and GPU proof, then register private experiment metadata."""
from pathlib import Path
import argparse
import hashlib
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--gpu-proof', type=Path, required=True)
parser.add_argument('--supersede-own-registration', action='store_true')
args = parser.parse_args()
path = args.build.resolve()
gpu_path = args.gpu_proof.resolve()
build = json.loads(path.read_text())
gpu = json.loads(gpu_path.read_text())
root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert gpu['result'] == 'POST_PRESENT_ACTUAL_GPU_PE6_COPY4_PRESENT6_ORDER6_PASS'
assert gpu['buildSha256'] == sha(path)
assert sha(public / 'verify_stock_completed_frame_gpu.py') == gpu['baseVerifierSha256']
assert sha(public / 'stock_post_present_gpu_cases.inc') == gpu['postCasesSha256']
assert sha(gpu['executablePath']) == gpu['executableSha256']
for file, digest in {**build['dependencies'], **build['retainedInputs'], **gpu['dependencies']}.items():
    assert sha(file) == digest
parent_path = root / 'window-pe-cadence/build.json'
parent = json.loads(parent_path.read_text())
parent_proof_path = parent_path.parent / 'component-verification.json'
parent_proof = json.loads(parent_proof_path.read_text())
assert sha(parent_path) == build['parentBuildSha256'] == parent_proof['buildSha256']
assert parent_proof['result'] == 'PE_CADENCE_GPU16_SETTINGS3_RETAINED_PARENT_COMPONENTS_VERIFIED'
assert build['archivePath'] == parent['archivePath'] and build['archiveSha256'] == parent['archiveSha256']
assert sha(build['archivePath']) == parent['archiveSha256']
assert build['members'] == parent['members']
old_main = next(arg for arg in parent['linkCommand'] if Path(arg).name == 'main.cpp.o')
expected = list(parent['linkCommand'])
expected[expected.index(old_main)] = build['changes']['main.cpp']['objectPath']
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
exe = Path(build['executablePath']).resolve()
assert exe.name == 'OpenSHSMStockPostPresentDrain' and exe.parent == path.parent
assert exe.parent.parent == Path('/private/tmp') and re.fullmatch(r'openshsm-post-present-[A-Za-z0-9_-]+', exe.parent.name)
assert sha(exe) == build['executableSha256']
report = {'result': 'POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED',
    'buildSha256': sha(path), 'gpuProofPath': str(gpu_path), 'gpuProofSha256': sha(gpu_path),
    'parentComponentSha256': sha(parent_proof_path),
    'dependencies': {str(file): sha(file) for file in [Path(__file__).resolve(), parent_path, parent_proof_path,
        public / 'verify_stock_post_present_gpu.py', public / 'stock_post_present_gpu_cases.inc']},
    'limits': ['Only main object changes, entire archive/CPU/texture/VI/PE/guest objects exact parent bytes.',
        'Actual extracted primary/presentation GL PE6/copy4/presentation6/post-swap6 pass; primary preserves pending ready copy.',
        'CPU/texture/timer evidence inherited, not rerun; whole-game interleaving/cadence/coherence/audio acceptance pending.',
        'Private experiment registration only, not default/public release or original Wii scheduling equivalence.']}
output = root / 'window-post-present'
output.mkdir(exist_ok=True)
if args.supersede_own_registration:
    prior_build = json.loads((output / 'build.json').read_text())
    prior_component = json.loads((output / 'component-verification.json').read_text())
    assert prior_component['buildSha256'] == sha(output / 'build.json')
    assert prior_component['result'] == report['result']
    prior_exe = Path(prior_build['executablePath'])
    assert prior_exe.name == exe.name and prior_exe.parent.parent == Path('/private/tmp')
    assert re.fullmatch(r'openshsm-post-present-[A-Za-z0-9_-]+', prior_exe.parent.name)
    assert sha(prior_exe) == prior_build['executableSha256']
for name, content in [('build.json', path.read_bytes()),
    ('component-verification.json', (json.dumps(report, indent=2) + '\n').encode())]:
    target = output / name
    assert args.supersede_own_registration or not target.exists() or target.read_bytes() == content
    if args.supersede_own_registration or not target.exists():
        target.write_bytes(content)
print(report['result'], output)
