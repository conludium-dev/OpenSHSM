"""Check observer-only delta and real GPU endpoints in three settings."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
args = parser.parse_args()
build_path = args.build.resolve()
build = json.loads(build_path.read_text())
root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent_path = root / 'window-completed-frame/build.json'
parent = json.loads(parent_path.read_text())
parent_proof = parent_path.parent / 'component-verification.json'
proof = json.loads(parent_proof.read_text())
assert proof['buildSha256'] == sha(parent_path) == build['parentBuildSha256']
assert proof['result'] == 'COMPLETED_FRAME_GL172_EVICTION1600_GPU16_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(path) == digest
assert sha(build['originalSourcePath']) == build['originalSourceSha256']
text = Path(build['originalSourcePath']).read_text()
for before, after in build['patches']:
    assert text.count(before) == 1
    text = text.replace(before, after, 1)
assert '#include "stock_pe_cadence_observation.h"\n#include <cstdio>\n' + text == Path(build['sourcePath']).read_text()
assert sha(build['sourcePath']) == build['sourceSha256']
assert sha(build['objectPath']) == build['objectSha256']
assert sha(build['archivePath']) == build['archiveSha256']
assert sha(build['executablePath']) == build['executableSha256']
for member, digest in build['members'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', build['archivePath'], member])
    assert hashlib.sha256(data).hexdigest() == digest
    if member != 'gx.cpp.o':
        assert data == subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], member])
expected = list(parent['linkCommand'])
expected[expected.index(parent['archivePath'])] = build['archivePath']
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
base = public / 'verify_stock_completed_frame_gpu.py'
script = base.read_text()
script = script[script.index("cache = Path(tempfile.mkdtemp"):]
script = script.replace("build['changes']['main.cpp']", "parent['changes']['main.cpp']")
old = "run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=60)"
assert script.count(old) == 1
script = script.replace(old, "if setting is not None:\n    env['NWII_PE_CADENCE_AFTER_MS'] = setting\n" + old)
records = []
endpoints = []
for label, setting in [('disabled', None), ('enabled', '0'), ('invalid', 'invalid')]:
    scope = dict(build=build, parent=parent, build_path=build_path, root=root, public=public,
        sha=sha, Path=Path, hashlib=hashlib, json=json, subprocess=subprocess, setting=setting,
        __file__=str(Path(__file__).resolve()))
    exec(compile('import os\nimport tempfile\n' + script, str(base), 'exec'), scope)
    report = json.loads(scope['path'].read_text())
    lines = report['stdout'].splitlines()
    diagnostic = [line for line in lines if line.startswith('[PECadence')]
    assert bool(diagnostic) == (setting == '0')
    endpoints.append('\n'.join(line for line in lines if not line.startswith('[PECadence')))
    records.append({'setting': label, 'proofPath': str(scope['path']), 'proofSha256': sha(scope['path']),
        'diagnosticLines': len(diagnostic)})
assert endpoints[0] == endpoints[1] == endpoints[2]
report = {'result': 'PE_CADENCE_GPU16_SETTINGS3_RETAINED_PARENT_COMPONENTS_VERIFIED',
    'buildSha256': sha(build_path), 'parentComponentSha256': sha(parent_proof), 'records': records,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), base, parent_path, parent_proof]},
    'limits': ['Real GPU PE6/copy4/presentation6 pass disabled/enabled/invalid; diagnostic-free outputs identical.',
        'Only observational GX member changes; CPU/texture/VI tests inherited through exact unchanged members/main, not rerun here.',
        'No full original guest latency, observer performance neutrality or live visual/audio acceptance.']}
path = build_path.parent / 'component-verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
