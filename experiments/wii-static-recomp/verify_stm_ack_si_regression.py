"""Re-link existing queued SI oracle with the actual new ACK objects/profile disabled."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'stm-irq-native-ack'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'attempt.json').read_text())
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
(output / 'queue-context.h').write_bytes((root / 'si-queue-native/queue-context.h').read_bytes())
prefix = (root / 'si-vector-native/si-query-host.cpp').read_text().split('int unused_getid_main(', 1)[0]
host = output / 'si-regression-host.cpp'
host.write_text('#include "finite_mem2_clear.h"\n#include "sram_frontend.h"\n#include "ipc_ack_frontend.h"\n#include "queue-context.h"\n' +
    prefix + (experiment / 'si_queue_host.cpp').read_text())
sources = [host, output / 'processor_adapter.cpp', output / 'ipc_reset_backend.cpp', output / 'ai_mask_backend.cpp',
    output / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
    runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'si-regression'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(output / 'finite_mem2_clear.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    '-I', str(output), '-I', str(experiment), '-I', str(root / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in build['records']], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'si-regression-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'si-regression.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr
oracle_path = root / 'dolphin-si-queue/comparison.json'
oracle = json.loads(oracle_path.read_text())
lines = result.stdout.splitlines()
assert len(lines) == 16
for index, state in enumerate(oracle['states']):
    values = list(map(int, lines[index].split()[2:]))
    context = list(state['context'][:8])
    context[1] = 0x807f0000
    assert values == context + state['completed'] + [state['scalar'][18], (index + 1) * 4, (index + 1) * 4]
guards = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'], capture_output=True, text=True, timeout=30)
assert guards.returncode == 0 and guards.stdout == 'SI_QUEUE_GUARDS 12\n' and not guards.stderr
(output / 'si-regression.json').write_text(json.dumps({'result': 'NEW_ACK_OBJECTS_SI16_64_TYPES_ORIGINAL_MATCH_12_GUARDS',
    'verifierSha256': sha(Path(__file__)), 'attemptSha256': sha(output / 'attempt.json'), 'oracleSha256': sha(oracle_path),
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'logSha256': sha(output / 'si-regression.log'), 'limits': ['Old SI branch on SAME new objects, IPC flag disabled; no combined-device concurrency proof.']}, indent=2) + '\n')
print('PASS same new ACK objects: SI16/64types-original endpoints;12guards')
