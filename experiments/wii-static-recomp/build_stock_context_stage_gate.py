"""Omit four always-rejected native diagnostic calls in one current guest unit."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent_path = root / 'window-post-present/build.json'
parent = json.loads(parent_path.read_text())
proof_path = parent_path.parent / 'component-verification.json'
proof = json.loads(proof_path.read_text())
assert proof['buildSha256'] == sha(parent_path)
assert proof['result'] == 'POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED'
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(path) == digest
old_obj = next(Path(arg) for arg in parent['linkCommand'] if Path(arg).name == 'output_38.cpp.o')
original = old_obj.with_suffix('')
source_proof_path = root / 'headless-sc-pc/build.json'
source_proof = json.loads(source_proof_path.read_text())
assert sha(original) == source_proof['sourceSha256'] and sha(old_obj) == source_proof['objectSha256']
header = public / 'stock_context_observation.h'
before = '''    const char* prefix = std::getenv("NWII_THPDUMP");
    if (!prefix || stage > 3) {
        return;
    }'''
text = header.read_text()
assert text.count(before) == 1
calls = [(4, '80212FA0'), (5, '80212FC4'), (6, '80212FC4'), (7, '80212FC8')]
patches = [[f'    stock_loading_observation::observe_context(ctx, {stage}, 0x{pc});\n', '']
    for stage, pc in calls]
source_text = original.read_text()
for old, new in patches:
    assert source_text.count(old) == 1
    source_text = source_text.replace(old, new, 1)
cache = Path(tempfile.mkdtemp(prefix='openshsm-context-stage-gate-', dir='/private/tmp'))
source, obj = cache / original.name, cache / old_obj.name
source.write_text(source_text)
flags_path = root / 'window-fp-guard/output_38.cpp.record.json'
flags = json.loads(flags_path.read_text())['arguments']
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(cache), *flags,
    '-H', '-c', str(source), '-o', str(obj)]
run = subprocess.run(command, capture_output=True, text=True, timeout=180)
(cache / 'compile.log').write_text(run.stdout + run.stderr)
assert run.returncode == 0, run.stderr[-3000:]
assert str(header) in run.stderr
link = list(parent['linkCommand'])
link[link.index(str(old_obj))] = str(obj)
exe = cache / 'OpenSHSMStockContextStageGate'
link[link.index('-o') + 1] = str(exe)
run = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert run.returncode == 0, run.stderr[-3000:]
retained = dict(parent['retainedInputs'])
del retained[str(old_obj)]
retained[parent['archivePath']] = parent['archiveSha256']
retained[parent['changes']['main.cpp']['objectPath']] = parent['changes']['main.cpp']['objectSha256']
report = {'result': 'CONTEXT_STAGE_GATE_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'sourcePath': str(source), 'sourceSha256': sha(source), 'originalSourcePath': str(original),
    'originalObjectPath': str(old_obj), 'objectPath': str(obj), 'objectSha256': sha(obj),
    'observerHeaderPath': str(header), 'observerHeaderSha256': sha(header), 'sourcePatches': patches,
    'compileCommand': command, 'linkCommand': link, 'executablePath': str(exe), 'executableSha256': sha(exe),
    'archivePath': parent['archivePath'], 'archiveSha256': parent['archiveSha256'], 'retainedInputs': retained,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), header,
        public / 'stock_loading_observation.h', proof_path, source_proof_path, flags_path]},
    'limits': ['Only output38 recompiled; exactly four native observer calls with always-rejected stages4..7 omitted.',
        'Common observer header/inline definition/shared counters unchanged, no divergent definitions across translation units.',
        'Stages0..3 still read current environment each call; no cached environment semantics or game/cache/callback/clock bypass.',
        'All original PPC cache-range loop/register/CTR/instruction counting/SC/IRQ operations retained.',
        'Runtime/observer/native/live endpoints and performance unverified, not registered/default/promoted.']}
path = cache / 'build.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
