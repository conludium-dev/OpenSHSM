"""Permit a private sampling-only copy after independent section/signature checks."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--proof', type=Path, required=True)
args = parser.parse_args()
path = args.proof.resolve()
proof = json.loads(path.read_text())
assert proof['result'] == 'DEBUG_MAP_REMOVED_LOADED_SECTIONS_IDENTICAL_SAMPLING_CANDIDATE'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
for file, digest in proof['dependencies'].items():
    assert sha(file) == digest
root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
parent_path = root / 'window-post-present/build.json'
parent = json.loads(parent_path.read_text())
exe = Path(proof['executablePath']).resolve()
assert exe.name == 'OpenSHSMStockSampleSymbols' and exe.parent.parent == Path('/private/tmp')
assert re.fullmatch(r'openshsm-sample-symbols-[A-Za-z0-9_-]+', exe.parent.name)
assert sha(exe) == proof['executableSha256']
base = public / 'prepare_stock_sample_symbols.py'
text = base.read_text()
scope = {'struct': struct, 'hashlib': hashlib}
exec(compile(text[text.index('def sections(path):'):text.index('before, after = sections(original)')], str(base), 'exec'), scope)
assert scope['sections'](Path(parent['executablePath'])) == scope['sections'](exe) == proof['sections']
subprocess.run(['/usr/bin/codesign', '--verify', str(exe)], check=True, capture_output=True, timeout=30)
build = dict(parent)
build.update(result='SAMPLE_SYMBOLS_METADATA_VARIANT_NOT_RUNTIME_VERIFIED',
    sourceBuildSha256=sha(parent_path), executablePath=str(exe), executableSha256=sha(exe),
    metadataCommand=proof['command'], metadataProofPath=str(path), metadataProofSha256=sha(path))
content = (json.dumps(build, indent=2) + '\n').encode()
report = {'result': 'SAMPLE_SYMBOLS_SECTIONS_SIGNATURE_VERIFIED_FOR_PROFILING_ONLY',
    'buildSha256': hashlib.sha256(content).hexdigest(), 'proofPath': str(path), 'proofSha256': sha(path),
    'dependencies': {str(file): sha(file) for file in [Path(__file__).resolve(), base, parent_path]},
    'limits': ['Only sampling admission; no claim stripped loader/game/visual/audio acceptance or default promotion.',
        'Parent link/source provenance inherited; actual variant creation is strip metadata command, not relink.',
        'All named loaded sections exact and signature valid; dynamic link-edit metadata not fully independently decoded.']}
output = root / 'window-sample-symbols'
output.mkdir(exist_ok=True)
for name, data in [('build.json', content), ('component-verification.json', (json.dumps(report, indent=2) + '\n').encode())]:
    target = output / name
    assert not target.exists() or target.read_bytes() == data
    if not target.exists():
        target.write_bytes(data)
print(report['result'], output)
