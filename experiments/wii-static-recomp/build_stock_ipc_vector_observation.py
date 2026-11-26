"""Observe original IPC reply vector operands; no cache/queue/IRQ bypass."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-ipc-vector-observe'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'window-nand-hierarchy/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected, path
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected, path
command = list(base['linkCommand'])
original_obj = next(Path(arg) for arg in command if Path(arg).name == 'output_40.cpp.o')
original = original_obj.with_suffix('')
record_path = original.with_name('output_40.cpp.record.json')
record = json.loads(record_path.read_text())
assert sha(original) == record['sourceSha256'] and sha(original_obj) == record['objectSha256']
text = original.read_text()
marker = 'loc_80241E08: ;\n'
assert text.count(marker) == 1
text = '#include "stock_ipc_vector_observation.h"\n' + text.replace(marker,
    marker + '    openshsm::experiment::observe_ipc_vector(ctx);\n')
source, obj = output / 'output_40.cpp', output / 'output_40.cpp.o'
source.write_text(text)
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command[command.index(str(original_obj))] = str(obj)
exe = output / 'OpenSHSMStockIPCVectorObserve'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
(output / 'build.json').write_text(json.dumps({'result': 'IPC_VECTOR_OBSERVER_BUILT_EXECUTION_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'originalRecordSha256': sha(record_path), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'executableSha256': sha(exe), 'linkCommand': command,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_ipc_vector_observation.h']},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(obj)},
    'limits': ['Bounded RAM-only operand snapshots at80241E08; no cache loop, original request, queue or IRQ behavior replaced.',
        'Built observer alone does not prove profile completion, SDK fidelity or rendering correctness.']}, indent=2) + '\n')
print('IPC_VECTOR_OBSERVER_BUILT_EXECUTION_UNVERIFIED')
