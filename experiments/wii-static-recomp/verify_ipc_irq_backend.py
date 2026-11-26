"""Check latched IPC flags and existing PI/scheduler ordering against retained original traces."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'ipc-irq-backend'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ipc_irq_dolphin.py')], check=True)
oracle_path = private / 'dolphin-ipc-irq/comparison.json'
oracle = json.loads(oracle_path.read_text())
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sources = [experiment / 'ipc_irq_probe.cpp', upstream / 'src/hw/hw_pi.cpp',
           upstream / 'src/hw/mmio_dispatcher.cpp', upstream / 'src/core/event_scheduler.cpp']
inputs = ''.join(f"{r['index']} {r['controlBefore']} {r['value']} {r['request']} {int(r['stage'] == 'reply')}\n" for r in oracle['observations'])
expected = [[r['index'], r['controlAfter'], r['causeAfter'], r['causeAfterFlagClear'], r['controlAfterFlagClear'],
             r['messageAfterFlagClear'], r['causeAfterDelay'], r['controlAfterDelay'], r['messageAfterDelay']] for r in oracle['observations']]
results = []
for mutant in (False, True):
    exe = output / ('sync-clear-mutant' if mutant else 'ipc-irq-probe')
    build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O2', '-include', 'bit',
                            *(['-DSHSM_SYNC_IRQ_CLEAR_MUTANT'] if mutant else []), '-I', str(experiment),
                            '-I', str(upstream / 'include'), '-I', str(upstream / 'src/hw'), *map(str, sources), '-o', str(exe)],
                           capture_output=True, text=True, timeout=60)
    (output / (exe.name + '.build.log')).write_text(build.stdout + build.stderr)
    assert build.returncode == 0, build.stderr
    native = subprocess.run([str(exe.resolve())], input=inputs, capture_output=True, text=True, timeout=30)
    (output / (exe.name + '.log')).write_text(native.stdout + native.stderr)
    assert native.returncode == 0 and 'IPC_IRQ_REFUSAL 1\n' in native.stdout
    rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('IPC_IRQ ')]
    assert len(rows) == 8
    if mutant:
        assert all(row != wanted and row[3] == 0x10000 for row, wanted in zip(rows, expected))
    else:
        assert rows == expected, (rows, expected)
    results.append({'mutant': mutant, 'executableSha256': sha(exe), 'logSha256': sha(output / (exe.name + '.log'))})
report = {'result': 'LATCHED_IPC_IRQ_PI_CAUSAL8_ORIGINAL_MATCH_SYNC_MUTANT8_DETECTED', 'cases': 8,
          'synchronousClearMutantMismatches': 8, 'refusalCases': 1, 'results': results,
          'oracleSha256': sha(oracle_path), 'backendSha256': sha(experiment / 'ipc_reset_backend.cpp'),
          'headerSha256': sha(experiment / 'ipc_reset_backend.h'), 'sources': {str(p): sha(p) for p in sources},
          'vendorSha256': sha(upstream / 'src/hw/hw_ipc.cpp'), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Existing vendor IPC storage/PI/EventScheduler; one experimental IRQFLAG state, no second runtime.',
                     'ACK/reply states and released reply are provided fixtures; no original native request producer/IOS queue integration.',
                     'Adapter ticks1/2 represent measured causal ordering, not Dolphin cycle count or physical Wii timing.',
                     'PI cause projection only; original IRQ vector/thread delivery/cache/full boot remain unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS8 original latched/deferred IRQ states, sync-clear mutant8 detected; no vector/boot activation')
