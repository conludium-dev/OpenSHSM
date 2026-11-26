"""Reproduce current parse-ahead shader state leakage without changing runtime policy."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

project = Path(__file__).resolve().parents[2]
root = project / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
build_path = root / 'window-context-stage/build.json'
component_path = build_path.parent / 'component-verification.json'
build = json.loads(build_path.read_text())
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['result'] == 'CONTEXT_STAGE_CACHE234_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'
assert sha(build['archivePath']) == build['archiveSha256']
assert all(sha(path) == value for path, value in build['retainedInputs'].items())
parser_build_path = root / 'window-pe-execute/build.json'
parser_record = json.loads(parser_build_path.read_text())['changes']['fifo_parser.cpp']
archive = build['archivePath']
parser_member = subprocess.check_output(['/usr/bin/ar', '-p', archive, 'fifo_parser.cpp.o'])
assert hashlib.sha256(parser_member).hexdigest() == parser_record['objectSha256']
assert sha(parser_record['sourcePath']) == parser_record['sourceSha256']
source_text = Path(parser_record['sourcePath']).read_text()
assert 'if (!no_seed)\n            g_state.bp[reg] = val;' in source_text
shader_build_path = root / 'headless-tev-banks/build.json'
shader_record = next(row for row in json.loads(shader_build_path.read_text())['compiled']
    if row['member'] == 'tev_shader_gen.cpp.o')
shader_source = root / 'headless-tev-banks/tev_shader_gen.cpp'
shader_member = subprocess.check_output(['/usr/bin/ar', '-p', archive, 'tev_shader_gen.cpp.o'])
assert hashlib.sha256(shader_member).hexdigest() == shader_record['objectSha256']
assert sha(shader_source) == shader_record['sourceSha256']
state_header = root / 'headless-tev-banks/include/runtime/gx_state.h'
flags_path = root / 'window-movie-late/build.json'
flags = json.loads(flags_path.read_text())['changes']['37']['arguments']
probe = public / 'stock_bp_seed_order_probe.cpp'
cache = Path(tempfile.mkdtemp(prefix='openshsm-bp-seed-order-', dir='/private/tmp'))
obj = cache / 'probe.cpp.o'
compile_command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
    '-UNDEBUG', '-c', str(probe), '-o', str(obj)]
compile_command[1:1] = ['-I', str(root / 'headless-tev-banks/include')]
compile_command.insert(1, '-H')
compiled = subprocess.run(compile_command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
assert str(state_header) in compiled.stderr
(cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
link = list(build['linkCommand'])
main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
link.insert(1, str(obj))
exe = cache / 'bp-seed-order-probe'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
results = []
for no_seed in (False, True):
    env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
    if no_seed:
        env['NWII_NOSEED'] = '1'
    run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0 and 'ACTUAL_LINKED_BP_KONST_FUTURE_STATE_SEED_CONTROL_PASS8' in run.stdout, run.stdout + run.stderr
    results.append({'noSeedControl': no_seed, 'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr})
report = {'result': 'CURRENT_BP_PARSE_AHEAD_KONST_SHADER_LEAK_REPRODUCED8_WITH_NOSEED_CONTROL8',
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), probe, build_path,
        component_path, parser_build_path, Path(parser_record['sourcePath']), flags_path,
        shader_build_path, shader_source, state_header, root / 'headless-tev-banks/contract-entry.cpp.o']},
    'archivePath': archive, 'archiveSha256': sha(archive), 'parserMemberSha256': hashlib.sha256(parser_member).hexdigest(),
    'shaderMemberSha256': hashlib.sha256(shader_member).hexdigest(),
    'compileCommand': compile_command, 'linkCommand': link,
    'executablePath': str(exe), 'executableSha256': sha(exe), 'runs': results,
    'limits': ['Actual current parser and generator linked, synthetic BP F6..FD inputs, no GL draw.',
        'NOSEED is an existing environment control in the probe only, not a changed game/default setting.',
        'No proof these exact writes cause the observed title band or that disabling seeding is a complete fix.',
        'Masked parser writes still require ordered parse state; no blanket NOSEED promotion or Wii behavior claim.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps(results, indent=2))
