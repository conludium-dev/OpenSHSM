"""Private RAM-first read32 candidate in measured entropy function only."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

project = Path(__file__).resolve().parents[2]
root = project / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent_path = root / 'window-bp-order/build.json'
parent = json.loads(parent_path.read_text())
component_path = parent_path.parent / 'component-verification.json'
assert json.loads(component_path.read_text())['buildSha256'] == sha(parent_path)
assert sha(parent['archivePath']) == parent['archiveSha256']
assert all(sha(path) == digest for path, digest in parent['retainedInputs'].items())
recipe_path = root / 'window-movie-late/build.json'
record = json.loads(recipe_path.read_text())['changes']['37']
old_obj = Path(next(arg for arg in parent['linkCommand'] if Path(arg).name == 'output_37.cpp.o'))
original = old_obj.with_suffix('')
assert sha(original) == record['sourceSha256'] and sha(old_obj) == record['objectSha256']
text = original.read_text()
start = text.index('void func_8020BDB0(CPUContext& ctx) {')
end = text.index('\nvoid func_', start + 1)
before = text[start:end]
count = before.count('ctx.mmu.read32(')
assert count > 0
after = before.replace('ctx.mmu.read32(', 'stock_entropy_read32(ctx.mmu, ')
assert after.count('process_pending_callbacks') == before.count('process_pending_callbacks') == 12
assert after.count('Spinning at PC:') == before.count('Spinning at PC:') == 12
text = text[:start] + after + text[end:]
cache = Path(tempfile.mkdtemp(prefix='openshsm-entropy-ram-', dir='/private/tmp'))
source, obj = cache / 'output_37.cpp', cache / 'output_37.cpp.o'
include = '#include "stock_entropy_ram_read.h"\n'
source.write_text(include + text)
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-I', str(original.parent), '-I', str(root / 'headless-psq-scale'), '-H', '-c', str(source), '-o', str(obj)]
print('Compiling owned RAM-first entropy reads', cache, 'sites', count, flush=True)
compiled = subprocess.run(command, capture_output=True, text=True, timeout=180)
(cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
assert str(public / 'stock_entropy_ram_read.h') in compiled.stderr
link = list(parent['linkCommand'])
link[link.index(str(old_obj))] = str(obj)
exe = cache / 'OpenSHSMStockEntropyRAMRead'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
retained = {path: digest for path, digest in parent['retainedInputs'].items() if path != str(old_obj)}
retained[parent['archivePath']] = parent['archiveSha256']
report = {'result': 'ENTROPY_RAM_FIRST_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'originalSourcePath': str(original), 'originalSourceSha256': sha(original), 'functionPatch': [before, after],
    'read32Sites': count, 'include': include, 'sourcePath': str(source), 'sourceSha256': sha(source),
    'objectPath': str(obj), 'objectSha256': sha(obj), 'compileCommand': command, 'linkCommand': link,
    'archivePath': parent['archivePath'], 'archiveSha256': parent['archiveSha256'],
    'executablePath': str(exe), 'executableSha256': sha(exe), 'retainedInputs': retained,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_entropy_ram_read.h',
        parent_path, component_path, recipe_path, original.parent / 'constant_fp_guard.h',
        root / 'headless-psq-scale/psq_scale.h', root / 'window-quantization/include/runtime/cpu_context.h']},
    'limits': ['Only BDB0 read32 calls replaced with RAM-first helper; all other operations/callbacks/console checks retained.',
        'Each read recomputes pointer, original padding/alias/null-low-word rules retained; non-RAM uses existing read32.',
        'No cached guest pointer/new memory service/MMIO bypass; boundary/native/GPU/live validation pending.',
        'Unregistered/notdefault/release, existing verified BP renderer retained.']}
path = cache / 'build.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
