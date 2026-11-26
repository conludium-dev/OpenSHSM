"""Compile original flush/syscall/vector with scoped entry and existing HID0 state."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-fpu-boot'
output = private / 'flush-syscall-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_flush_syscall_dolphin.py')], check=True)
build = json.loads((base / 'boot.json').read_text())
for name in ('mass_boot.cpp', 'loader-bat-seed.h'):
    (output / name).write_bytes((base / name).read_bytes())
transforms = [
    ('    // 0x80212FF8: 44000002\n    // sc (System Call)\n    nwii::runtime::handle_syscall(ctx);',
     '    // 0x80212FF8: 44000002\n    if (nwii::runtime::experiment_flush_syscall_enter(ctx, 0x80212ff8)) { return; }'),
    ('    // 0x8021A128: 7D50FBA6\n    nwii::runtime::experiment_write_hid0_spd(ctx, ctx.gpr[10]);',
     '    // 0x8021A128: 7D50FBA6\n    nwii::runtime::experiment_flush_hid0_write(ctx, ctx.gpr[10], 0x8021a128);'),
    ('    // 0x8021A130: 7C0004AC\n    // sync/cache instruction',
     '    // 0x8021A130: 7C0004AC\n    nwii::runtime::experiment_flush_sync(ctx);'),
    ('    // 0x8021A134: 7D30FBA6\n    nwii::runtime::experiment_write_hid0_spd(ctx, ctx.gpr[9]);',
     '    // 0x8021A134: 7D30FBA6\n    nwii::runtime::experiment_flush_hid0_write(ctx, ctx.gpr[9], 0x8021a134);'),
    ('    // 0x8021A138: 4C000064\n    {', '    // 0x8021A138: 4C000064\n    nwii::runtime::experiment_flush_return_guard(ctx);\n    {')
]
records = []
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] == 'output_63.cpp':
        text = Path(row['source']).read_text()
        for before, after in transforms:
            assert text.count(before) == 1
            text = text.replace(before, after)
        source = output / row['file']
        source.write_text(text)
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'ai_clock_profile.h'), '-include', str(experiment / 'flush_syscall.h'),
            '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / 'compile.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-2000:]
        record.update({'source': str(source), 'sourceSha256': sha(source), 'object': str(obj), 'objectSha256': sha(obj),
            'inputSource': row['source'], 'inputSourceSha256': row['sourceSha256']})
    records.append(record)
host = output / 'flush-host.cpp'
body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')
body = body.replace('    if (context.inst_count > 100000)', '    if (context.pc == 0x807f0000) { throw std::runtime_error("Flush oracle return sentinel"); }\n    if (context.inst_count > 100000)')
host.write_text('#include "ai_clock_profile.h"\n#include "sram_frontend.h"\n#include "flush_syscall.h"\n' + body + '\n' + (experiment / 'flush_syscall_host.cpp').read_text())
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp', runtime / 'src/core/loader.cpp',
    runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'flush-syscall-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_SI_EXTERNAL_DELIVERY',
    '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'),
    '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in records], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
(output / 'build.json').write_text(json.dumps({'result': 'FLUSH_NATIVE_REQUIRES_COMPARISON', 'returnCode': result.returncode,
    'builderSha256': sha(Path(__file__)), 'baseBootSha256': sha(base / 'boot.json'), 'records': records, 'transforms': transforms,
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'inputHashes': {str(experiment / name): sha(experiment / name) for name in ('exi_getid_host.cpp', 'flush_syscall_host.cpp', 'flush_syscall.h', 'bat_context.h')},
    'oracleSha256': sha(private / 'dolphin-flush-syscall/comparison.json')}, indent=2) + '\n')
print(result.stdout[-500:] + result.stderr)
assert result.returncode == 0
