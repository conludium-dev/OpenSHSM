"""Observe the actual caller/range before original cache work; never skip it."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-buffer-flush-observe'
output.mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
base_path = root / 'window-texture-observe/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
original_obj = next(Path(arg) for arg in command if Path(arg).name == 'output_64.cpp.o')
original = original_obj.with_suffix('')
record_path = original.with_name('output_64.cpp.record.json')
record = json.loads(record_path.read_text())
assert sha(original) == record['sourceSha256'] and sha(original_obj) == record['objectSha256']
text = original.read_text()
for label, entry in [('8035AEF8', 'true'), ('8035AF34', 'false')]:
    marker = f'loc_{label}: ;\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + f'    openshsm::experiment::observe_buffer_flush(ctx, {entry});\n')
text = '#include "stock_buffer_flush_observation.h"\n' + text
source, obj = output / 'output_64.cpp', output / 'output_64.cpp.o'
source.write_text(text)
def compile_file(src, target, timeout):
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
        '-c', str(src), '-o', str(target)], capture_output=True, text=True, timeout=timeout)
    (output / (target.name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
compile_file(source, obj, 180)
command[command.index(str(original_obj))] = str(obj)
exe = output / 'OpenSHSMStockBufferFlushObserve'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
probe_source, probe_obj = public / 'stock_buffer_flush_observation_probe.cpp', output / 'probe.cpp.o'
compile_file(probe_source, probe_obj, 60)
probe_command = list(command)
probe_command[probe_command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
probe_command.insert(1, str(probe_obj))
probe = output / 'observer-probe'
probe_command[probe_command.index('-o') + 1] = str(probe)
subprocess.run(probe_command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'BUFFER_FLUSH_OBSERVER_COMPONENT_PASS' in result.stdout, result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'BUFFER_FLUSH_OBSERVER_BUILT_LIVE_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'originalRecordSha256': sha(record_path), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'executableSha256': sha(exe), 'linkCommand': command,
    'probeExecutableSha256': sha(probe), 'probeLogSha256': sha(output / 'probe.log'),
    'dependencies': {str(p): sha(p) for p in [Path(__file__).resolve(), public / 'stock_buffer_flush_observation.h', probe_source]},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(obj)},
    'limits': ['Read-only two source labels;16normal+16abnormal each, RAM-only owner/stack reads.',
        'Original cache work/registers/return/IRQ/runtime retained; timing overhead not exact Wii timing.',
        'No buffer producer repair/render/profile acceptance from observer build.']}, indent=2) + '\n')
print('BUFFER_FLUSH_OBSERVER_BUILT_LIVE_UNVERIFIED')
