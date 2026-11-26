"""Private decoder delta: omit console-only spin checks in measured entropy function."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import tempfile

project = Path(__file__).resolve().parents[2]
root = project / 'work/private-game/static-recomp/stock-baseline'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent_path = root / 'window-bp-order/build.json'
parent = json.loads(parent_path.read_text())
component_path = parent_path.parent / 'component-verification.json'
assert json.loads(component_path.read_text())['buildSha256'] == sha(parent_path)
assert sha(parent['archivePath']) == parent['archiveSha256']
recipe_path = root / 'window-movie-late/build.json'
record = json.loads(recipe_path.read_text())['changes']['37']
old_obj = Path(next(arg for arg in parent['linkCommand'] if Path(arg).name == 'output_37.cpp.o'))
original = old_obj.with_suffix('')
assert sha(original) == record['sourceSha256'] and sha(old_obj) == record['objectSha256']
text = original.read_text()
start = text.index('void func_8020BDB0(CPUContext& ctx) {')
end = text.index('\nvoid func_', start + 1)
body = text[start:end]
lines = [line + '\n' for line in body.splitlines() if 'Spinning at PC:' in line]
assert len(lines) == 12 and body.count('process_pending_callbacks') == 12
assert all(re.fullmatch(r'    if \(\(ctx.inst_count % 10000000\) == 0\) \{ std::cout .*std::endl; \}\n', line) for line in lines)
patched = body
for line in lines:
    assert patched.count(line) == 1
    patched = patched.replace(line, '', 1)
assert patched.count('process_pending_callbacks') == 12
assert re.findall(r'// 0x[0-9A-F]{8}: [0-9A-F]{8}', body) == re.findall(r'// 0x[0-9A-F]{8}: [0-9A-F]{8}', patched)
text = text[:start] + patched + text[end:]
cache = Path(tempfile.mkdtemp(prefix='openshsm-entropy-spin-', dir='/private/tmp'))
source, obj = cache / 'output_37.cpp', cache / 'output_37.cpp.o'
source.write_text(text)
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-I', str(original.parent), '-I', str(root / 'headless-psq-scale'), '-c', str(source), '-o', str(obj)]
print('Compiling console-only entropy delta', cache, flush=True)
compiled = subprocess.run(command, capture_output=True, text=True, timeout=180)
(cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
link = list(parent['linkCommand'])
link[link.index(str(old_obj))] = str(obj)
exe = cache / 'OpenSHSMStockEntropySpinCleanup'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
retained = {path: digest for path, digest in parent['retainedInputs'].items() if path != str(old_obj)}
retained[parent['archivePath']] = parent['archiveSha256']
report = {'result': 'ENTROPY_SPIN_CONSOLE_ONLY_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'originalSourcePath': str(original), 'originalSourceSha256': sha(original), 'removedConsoleLines': lines,
    'sourcePath': str(source), 'sourceSha256': sha(source), 'objectPath': str(obj), 'objectSha256': sha(obj),
    'compileCommand': command, 'linkCommand': link, 'archivePath': parent['archivePath'], 'archiveSha256': parent['archiveSha256'],
    'executablePath': str(exe), 'executableSha256': sha(exe), 'retainedInputs': retained,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), parent_path, component_path,
        recipe_path, original.parent / 'constant_fp_guard.h', root / 'headless-psq-scale/psq_scale.h']},
    'limits': ['Only12 console spin/modulo checks in native entropy adapter removed; branch/PC/instruction count and12 callbacks retained.',
        'No original PPC/cache/IRQ/timebase/FP/MMU/renderer behavior intentionally changed, console diagnostics intentionally reduced.',
        'Actual endpoint/performance/CPU regression/live acceptance pending; not registered/default/release.']}
path = cache / 'build.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
