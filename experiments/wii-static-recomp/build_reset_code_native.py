"""Compile one measured PI read seam, preserving original reset-code branches."""
from pathlib import Path
import hashlib
import json
import subprocess
experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-uart-ri-boot'
output = private / 'reset-code-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_reset_code_dolphin.py')], check=True)
build = json.loads((base / 'boot.json').read_text())
for name in ('loader-bat-seed.h', 'mass_boot.cpp', 'memory-protection-bat-plan.h'):
    (output / name).write_bytes((base / name).read_bytes())
records = []
before = '    // 0x80219504: 80033024\n    ctx.gpr[0] = nwii::runtime::experiment_si_query_read32(ctx, ctx.gpr[3] + 12324, 0x80219504); // lwz r0, 12324(r3)'
after = before.replace('experiment_si_query_read32', 'experiment_reset_code_read32')
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = {key: row[key] for key in ('file', 'source', 'sourceSha256', 'object', 'objectSha256')}
    if row['file'] == 'output_63.cpp':
        text = Path(row['source']).read_text()
        assert text.count(before) == 1
        source = output / row['file']
        source.write_text(text.replace(before, after))
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'reset_code_frontend.h'), '-I', str(output), '-I', str(runtime / 'include'),
            '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / 'compile.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-2500:]
        record.update(source=str(source), sourceSha256=sha(source), object=str(obj), objectSha256=sha(obj))
    records.append(record)
prefix = (experiment / 'exi_getid_host.cpp').read_text()
prefix = prefix[:prefix.index('int main(int argc, char** argv)')]
host = output / 'reset-host.cpp'
host.write_text('#include "reset_code_frontend.h"\n#include "sram_frontend.h"\n' + prefix + (experiment / 'reset_code_host.cpp').read_text())
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    experiment / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
    runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'reset-code-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(experiment / 'reset_code_frontend.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER',
    '-DSHSM_CACHE_ADAPTER', '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'),
    '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in records], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
results = {}
for mode in ('normal', 'guards'):
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', *([] if mode == 'normal' else [mode])], capture_output=True, text=True, timeout=30)
    (output / (mode + '.log')).write_text(result.stdout + result.stderr)
    results[mode] = {'returnCode': result.returncode, 'logSha256': sha(output / (mode + '.log'))}
    print(mode, result.returncode, (result.stdout + result.stderr)[-200:])
(output / 'build.json').write_text(json.dumps({'result': 'RESET_CODE_NATIVE_REQUIRES_COMPARISON', 'builderSha256': sha(Path(__file__)),
    'records': records, 'sourceHashes': {str(path): sha(path) for path in sources}, 'results': results,
    'headerHashes': {str(path): sha(path) for path in experiment.glob('*.h')}, 'executableSha256': sha(exe),
    'before': before, 'after': after, 'baseBootSha256': sha(base / 'boot.json')}, indent=2) + '\n')
assert all(row['returnCode'] == 0 for row in results.values())
