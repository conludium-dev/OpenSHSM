"""Use measured Dolphin LAB dcbi contract at one original SDK cache instruction."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
subprocess.run(['python3', str(experiment / 'verify_di_cache_events_dolphin.py')], check=True)
parent = experiment / 'build_di_burst_es_boot.py'
body = parent.read_text().replace('mass-di-burst-es-boot', 'mass-di-burst-cache-boot')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
root = Path('work/private-game/static-recomp')
output = root / 'mass-di-burst-cache-boot'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
front = output / 'ipc_ack_frontend.h'
text = front.read_text()
assert text.count('#include "di_burst_es.h"') == 1
text = text.replace('#include "di_burst_es.h"', '#include "di_burst_es.h"\n#include "di_burst_cache_adapter.h"')
assert text.count('ipc.ppcControl == 0x34') == 3
front.write_text(text.replace('ipc.ppcControl == 0x34', 'experiment_di_burst_reply_ready(ipc)'))
external = output / 'si_external_delivery.h'
text = external.read_text()
text = text.replace('inline bool experiment_fs_prior_arm(uint32_t message, uint32_t arm);',
    'inline bool experiment_fs_prior_arm(uint32_t message, uint32_t arm);\ninline bool experiment_di_burst_reply_ready(const hw::ExperimentIpcSnapshot& ipc);')
assert text.count('ipc.ppcControl != 0x34') == 1 and text.count('ipc.ppcControl == 0x34') == 2
external.write_text(text.replace('ipc.ppcControl != 0x34', '!experiment_di_burst_reply_ready(ipc)').replace(
    'ipc.ppcControl == 0x34', 'experiment_di_burst_reply_ready(ipc)'))
(output / 'di_burst_cache_adapter.h').write_bytes((experiment / 'di_burst_cache_adapter.h').read_bytes())
row = next(row for row in build['records'] if row['file'] == 'output_63.cpp')
source = output / 'output_63.cpp'
text = Path(row['source']).read_text()
old = 'nwii::runtime::bat_memory_cache_operation(ctx, ctx.gpr[3], 470);'
start = text.index('void func_80212FA0(')
end = text.index('\nvoid func_', start + 1)
function = text[start:end]
assert function.count(old) == 1
source.write_text(text[:start] + function.replace(old, 'nwii::runtime::experiment_di_burst_cache_operation(ctx, ctx.gpr[3], 470);') + text[end:])
obj = output / 'output_63.cpp.o'
includes = ['-include', str(output / 'finite_mem2_clear.h'), '-I', str(output), '-I', str(experiment),
    '-I', str(root / 'mass-current'), '-I', str(runtime / 'include')]
compiled = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
    *includes, '-include', str(front), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'output_63.cpp.compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
row.update(source=str(source), sourceSha256=sha(source), object=str(obj), objectSha256=sha(obj))
for name in ('output_62.cpp', 'output_65.cpp', 'output_67.cpp', 'output_68.cpp'):
    row = next(row for row in build['records'] if row['file'] == name)
    source = Path(row['source'])
    if name == 'output_68.cpp':
        source = output / name
        text = Path(row['source']).read_text()
        assert text.count('loc_802497D4: ;') == 1
        source.write_text(text.replace('loc_802497D4: ;', 'loc_802497D4: ;\n    nwii::runtime::experiment_di_burst_es_return_observe(ctx);'))
    obj = output / (name + '.o')
    compiled = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
        *includes, '-include', str(front), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / (name + '.compile.log')).write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr[-3000:]
    row.update(source=str(source), sourceSha256=sha(source), object=str(obj), objectSha256=sha(obj))
sources = [Path(path) for path in build['sourceHashes'] if Path(path).name not in ('mass_boot.cpp', 'ipc_event_order_probe.cpp')]
exe = output / 'openshsm-mass-boot'
linked = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', *includes,
    '-include', str(output / 'interrupt_enable_observer.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER',
    '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[record['object'] for record in build['records']],
    '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(linked.stdout + linked.stderr)
assert linked.returncode == 0, linked.stderr[-3000:]
build.update(builderSha256=sha(Path(__file__)), executableSha256=sha(exe),
    sourceHashes={path: sha(Path(path)) for path in build['sourceHashes']},
    headerHashes={str(path): sha(path) for path in output.glob('*.h')},
    limits=['Only original DCInvalidateRange dcbi binding changed to bounded observed-unchanged Dolphin LAB input contract.',
        'Not generalized unmapped cache semantics or physical Wii proof. No PPC register/MSR/address rewriting. Five objects rebuilt/120 retained; ES return observer read-only.'])
(output / 'build.json').write_text(json.dumps(build, indent=2) + '\n')
for mode in ('live', 'disabled'):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_DI86_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(root / 'sram-native/settings.bin')], env=env, capture_output=True, text=True, timeout=30)
    (output / (mode + '-boot.log')).write_text(result.stdout + result.stderr)
    print(mode + ': ' + '\n'.join(line for line in result.stdout.splitlines() if line.startswith(('BOOT_BOUNDARY', 'BOOT_STM submitted=', 'DI86_SOURCE', 'DI_BURST_ES_REPLY', 'DI86_INPUT_DCBI'))))
