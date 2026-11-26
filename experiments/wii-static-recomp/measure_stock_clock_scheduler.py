"""Measure coarse actual-clock/scheduler/poll batches; never infer an exclusive live-game CPU fraction."""
from pathlib import Path
import hashlib
import json
import os
import re
import statistics
import subprocess
import tempfile
import shutil

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'clock-scheduler-batch'
output.mkdir(exist_ok=True)
prior_path = output / 'verification.json'
if prior_path.exists() and not (output / 'contaminated-constant-inst-count.json').exists():
    shutil.copyfile(prior_path, output / 'contaminated-constant-inst-count.json')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = root / 'window-dispatch-o2/build.json'
build = json.loads(build_path.read_text())
component_path = build_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'DISPATCH_O2_ROUTES_CALLBACK4_SDK7_SC3_LATE18_EQUAL'
assert component['buildSha256'] == sha(build_path)
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
ios_path = root / 'window-ios-o2/build.json'
ios = json.loads(ios_path.read_text())
flags = ios['arguments']
temporary = Path(tempfile.mkdtemp(prefix='openshsm-clock-scheduler-', dir='/private/tmp'))
source = public / 'stock_clock_scheduler_batch_probe.cpp'
obj, exe = temporary / 'probe.o', temporary / 'probe'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++',
    '-I', str(root / 'window-adma-deadline/include'), *flags,
    '-H', '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(temporary / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-2500:]
header = root / 'window-quantization/include/runtime/cpu_context.h'
assert '. ' + str(header) + '\n' in compiled.stderr
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(temporary / 'link.log').write_text(linked.stdout + linked.stderr)
assert linked.returncode == 0, linked.stderr[-2500:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env['NWII_WALLTB'] = '1'
log = temporary / 'run.log'
try:
    run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=45)
except subprocess.TimeoutExpired as error:
    partial = error.stdout or b''
    log.write_text(partial.decode(errors='replace') if isinstance(partial, bytes) else partial)
    (output / 'failed-observation.json').write_text(json.dumps({
        'result': 'COARSE_BATCH_TIMEOUT_INCOMPLETE', 'executablePath': str(exe),
        'logPath': str(log), 'logSha256': sha(log), 'seconds': 45,
        'limits': ['subprocess.run timed out and terminated owned child; no successful benchmark or game inference.']}, indent=2) + '\n')
    print(log.read_text()[-3000:])
    raise
log.write_text(run.stdout + run.stderr)
assert run.returncode == 0 and 'CLOCK_SCHEDULER_NATIVE_BATCH_PASS' in run.stdout, run.stdout + run.stderr
assert '[Heartbeat]' not in run.stdout and '[ExcTable]' not in run.stdout
rows = [{'iteration': int(iteration), 'case': case, 'calls': int(calls), 'wallNs': int(wall),
    'cpuNs': int(cpu), 'firings': int(firings)} for iteration, case, calls, wall, cpu, firings in re.findall(
    r'^BATCH (\d+) ([a-z0-9-]+) (\d+) (\d+) (\d+) (\d+)$', run.stdout, re.M)]
assert len(rows) == 55 and all(row['calls'] == 262144 for row in rows)
summary = {name: {'medianWallNsPerCall': statistics.median(row['wallNs'] / row['calls'] for row in rows if row['case'] == name),
    'medianCpuNsPerCall': statistics.median(row['cpuNs'] / row['calls'] for row in rows if row['case'] == name),
    'firingCounts': [row['firings'] for row in rows if row['case'] == name]}
    for name in sorted({row['case'] for row in rows})}
assert all(row['firings'] == 0 for row in rows if row['case'] != 'combined-vi-period')
assert any(row['firings'] > 0 for row in rows if row['case'] == 'combined-vi-period')
(output / 'verification.json').write_text(json.dumps({
    'result': 'CURRENT_CLOCK_SCHEDULER_POLL_COARSE_BATCHES55_ADVANCING_COUNTER_MEASURED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'iosBuildSha256': sha(ios_path),
    'sourceSha256': sha(source), 'headerPath': str(header), 'headerSha256': sha(header), 'objectSha256': sha(obj),
    'compileLogSha256': sha(temporary / 'compile.log'), 'executablePath': str(exe), 'executableSha256': sha(exe),
    'logPath': str(log), 'logSha256': sha(log), 'verifierSha256': sha(Path(__file__)),
    'flags': flags, 'linkCommand': command, 'rows': rows, 'summary': summary,
    'limits': ['Actual current CPUContext header resolved by compiler/current schedulerO2/IOSO2/master/helper archive retained.',
        'Batch262144 calls ×11cases ×5 alternating order; only batch-end wall/threadCPU clocks, no per-call observer.',
        'No-inline wrappers/function-pointer call/volatile sink/loop overhead included; empty baseline not exact subtractable constant.',
        'Callback probe increments instruction counter from12345; prior constant0 run hit diagnostic logging every call and is marked contaminated.',
        'Synthetic no active GUI/device IRQ queues; recurring test counts only callback, full IOS tests EE/DEC idle not original IRQ delivery.',
        'No original resources executed/changed, no exclusive live fraction or game FPS inference; coarse evidence selects next action.',
        'Large object/executable/log temporary/private; no runtime optimization/promotion/visual/audio/profile acceptance.']}, indent=2) + '\n')
print('CURRENT_CLOCK_SCHEDULER_POLL_COARSE_BATCHES55_ADVANCING_COUNTER_MEASURED')
print(json.dumps(summary, indent=2))
