"""Run whole compiled register helper and scoped guards against original cold-start observations."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-ipc-startup-boot'
output = root / 'ipc-startup-native'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
for path in base.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('mass_boot.cpp', 'processor_adapter.cpp', 'ipc_reset_backend.cpp', 'ai_mask_backend.cpp', 'dsp_startup_backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
prefix = (root / 'si-vector-native/si-query-host.cpp').read_text().split('int unused_getid_main(', 1)[0]
host = output / 'ipc-startup-host.cpp'
host.write_text('#include "finite_mem2_clear.h"\n#include "sram_frontend.h"\n#include "ipc_startup_frontend.h"\n' + prefix + (experiment / 'ipc_startup_host.cpp').read_text())
sources = [host, output / 'processor_adapter.cpp', output / 'ipc_reset_backend.cpp', output / 'ai_mask_backend.cpp',
    output / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
    runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'ipc-startup-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(output / 'finite_mem2_clear.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    '-I', str(output), '-I', str(experiment), '-I', str(root / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources),
    *[row['object'] for row in build['records']], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
oracle_path = root / 'dolphin-ipc-startup/comparison.json'
oracle = json.loads(oracle_path.read_text())
lines = result.stdout.splitlines()
assert len(lines) == 17 and lines[-1] == 'IPC_STARTUP_GUARDS 10'
for index, original in enumerate(oracle['states']):
    tokens = lines[index].split()
    assert tokens[:2] == ['IPC_STARTUP_CASE', str(index)]
    expected = list(original)
    expected[8] = 0x80242140
    assert list(map(int, tokens[2:])) == expected
(output / 'comparison.json').write_text(json.dumps({'result': 'WHOLE_COMPILED_IPC_COLD38_16_ABI_CONTROL_PI10_GUARDS_PASS',
    'runnerSha256': sha(Path(__file__)), 'inputBuildSha256': sha(base / 'build.json'), 'oracleSha256': sha(oracle_path),
    'hostSourceSha256': sha(host), 'executableSha256': sha(exe), 'logSha256': sha(output / 'native.log'),
    'limits': ['Original return target replaced only by observed caller80242140; helper remains whole compiled original.',
        'Lab control6 resets between calls; reset-button PI level10000 allowed only when masked, as in Dolphin oracle.',
        'Cold control no-request profile only, not full IPC client/IRQ/request handling.']}, indent=2) + '\n')
print('PASS16whole compiled IPC cold38 originalABI/control/PI;10state-preserving startup guards')
