"""Re-run old RI-off UART/GetID and the whole memory procedure with current objects."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'uart-ri-native'
output = private / 'uart-ri-regressions'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
for name in ('loader-bat-seed.h', 'mass_boot.cpp', 'memory-protection-bat-plan.h'):
    (output / name).write_bytes((base / name).read_bytes())
prefix = (experiment / 'exi_getid_host.cpp').read_text()
prefix = prefix[:prefix.index('int main(int argc, char** argv)')]
reports = {}
for name in ('uart', 'getid', 'memory'):
    host = output / (name + '-host.cpp')
    body = (experiment / ('uart_host.cpp' if name == 'uart' else 'memory_protection_host.cpp')).read_text() if name != 'getid' else (experiment / 'exi_getid_host.cpp').read_text().split('int main(int argc, char** argv)', 1)[1]
    if name == 'getid':
        body = 'int main(int argc, char** argv)' + body
    chosen_prefix = prefix
    if name == 'memory':
        chosen_prefix = prefix.replace('    if (context.inst_count > 100000)', '    if (context.pc == 0x807f0000) { throw std::runtime_error("MI oracle return sentinel"); }\n    if (context.inst_count > 100000)')
    host.write_text('#include "memory_protection_frontend.h"\n#include "sram_frontend.h"\n' + chosen_prefix + body)
    sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
        experiment / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
        runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
    exe = output / (name + '-probe')
    result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
        '-include', str(experiment / 'memory_protection_frontend.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER',
        '-DSHSM_CACHE_ADAPTER', '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'),
        '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
        *map(str, sources), *[row['object'] for row in build['records']], '-o', str(exe)], capture_output=True, text=True, timeout=180)
    (output / (name + '-build.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2500:]
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
    (output / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and not result.stderr, result.stdout[-600:] + result.stderr
    reference = private / ('uart-native/native.log' if name == 'uart' else 'exi-getid-native/native.log' if name == 'getid' else 'memory-protection-native/native.log')
    assert result.stdout == reference.read_text(), name
    reports[name] = {'executableSha256': sha(exe), 'logSha256': sha(output / (name + '.log')), 'referenceSha256': sha(reference)}
(output / 'verification.json').write_text(json.dumps({'result': 'RI_OPT_IN_DISABLED_UART16_GETID16_MEMORY16_REGRESSION_PASS',
    'runnerSha256': sha(Path(__file__)), 'inputBuildSha256': sha(base / 'build.json'), 'reports': reports,
    'limits': ['Same current objects, profile defaults disabled in old UART/GetID hosts; positive regressions only.',
        'Memory procedure compared against retained original-verified native result; no hardware/full-game proof.']}, indent=2) + '\n')
print('PASS RI opt-in retains default RI-off UART16/GetID16 and whole memory-protection16 results')
