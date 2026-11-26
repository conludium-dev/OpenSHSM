"""Reuse current boot objects with a private deterministic specialization of existing SI delivery."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-finite-mem2-boot'
output = private / 'si-queue-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_si_queue_dolphin.py')], check=True)
for path in experiment.glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('mass_boot.cpp', 'loader-bat-seed.h', 'memory-protection-bat-plan.h', 'memory_protection_frontend.h',
        'dc_zero_frontend.h', 'reset_code_frontend.h', 'finite_mem2_clear.h'):
    (output / name).write_bytes((base / name).read_bytes())
delivery = (experiment / 'si_external_delivery.h').read_text()
for before, after in [('hw::pi_intmr.load() != 8', 'hw::pi_intmr.load() != 0xf8'),
        ('0x00501000', '0x00492658'), ('0x80501000', '0x80492658'), ('0xfffff7ff', '0xf7fff7f0')]:
    assert before in delivery
    delivery = delivery.replace(before, after)
(output / 'si_external_delivery.h').write_text(delivery)
evidence = json.loads((private / 'mass-interrupt-context-observer/audit.json').read_text())
words = evidence['contextWords']
(output / 'queue-context.h').write_text('inline constexpr std::array<uint32_t, ' + str(len(words)) + '> queueContextWords{' + ','.join(hex(word) for word in words) + '};\n')
prefix = (private / 'si-vector-native/si-query-host.cpp').read_text().split('int unused_getid_main(', 1)[0]
host = output / 'si-queue-host.cpp'
host.write_text('#include "finite_mem2_clear.h"\n#include "sram_frontend.h"\n#include "queue-context.h"\n' + prefix + (experiment / 'si_queue_host.cpp').read_text())
build = json.loads((base / 'boot.json').read_text())
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name in ('processor_adapter.cpp', 'ipc_reset_backend.cpp', 'ai_mask_backend.cpp', 'dsp_startup_backend.cpp'):
    (output / name).write_bytes((experiment / name).read_bytes())
sources = [host, output / 'processor_adapter.cpp', output / 'ipc_reset_backend.cpp', output / 'ai_mask_backend.cpp',
    output / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
    runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'si-queue-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(output / 'finite_mem2_clear.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in build['records']], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
(output / 'build.json').write_text(json.dumps({'result': 'SI_QUEUE_NATIVE_REQUIRES_COMPARISON', 'builderSha256': sha(Path(__file__)),
    'baseBootSha256': sha(base / 'boot.json'), 'records': build['records'], 'returnCode': result.returncode,
    'sourceHashes': {str(path): sha(path) for path in sources}, 'headerHashes': {str(path): sha(path) for path in output.glob('*.h')},
    'executableSha256': sha(exe), 'contextEvidenceSha256': sha(private / 'mass-interrupt-context-observer/audit.json'),
    'limits': ['Existing delivery privately specialized to measured profile; public old profile unchanged/no second runtime.',
        'Current125objects reused; prepared vector/context/queue, fixed post-due clock800000 is explicit PC fixture.']}, indent=2) + '\n')
print(result.stdout[-1500:] + result.stderr)
assert result.returncode == 0
