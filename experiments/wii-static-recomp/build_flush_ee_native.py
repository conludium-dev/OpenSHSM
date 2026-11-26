"""Rebuild only current flush-owning batches with the bounded existing-mechanism profile."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-ipc-startup-boot'
output = root / 'flush-ee-profile'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_flush_ee_dolphin.py')], check=True)
subprocess.run(['python3', str(experiment / 'build_flush_ee_profile.py')], check=True)
build = json.loads((base / 'build.json').read_text())
records = []
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] in ('output_63.cpp', 'output_64.cpp'):
        target = output / row['file']
        target.write_bytes(Path(row['source']).read_bytes())
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(output / 'finite_mem2_clear.h'), '-I', str(output), '-I', str(experiment),
            '-I', str(runtime / 'include'), '-I', str(root / 'mass-current'), '-c', str(target), '-o', str(obj)],
            capture_output=True, text=True, timeout=180)
        (output / (row['file'] + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-2500:]
        record.update(source=str(target), sourceSha256=sha(target), object=str(obj), objectSha256=sha(obj))
    records.append(record)
prefix = (root / 'si-vector-native/si-query-host.cpp').read_text().split('int unused_getid_main(', 1)[0]
prefix = prefix.replace('0x807f0000', '0x8024262c').replace('SI IRQ oracle return sentinel', 'Flush oracle return sentinel')
body = (experiment / 'flush_syscall_host.cpp').read_text().replace('0x2032', '0xa032').replace('0x807f0000', '0x8024262c')
body = body.replace('    context.flushSyscall = true;', '    context.flushSyscall = true;\n    experimentFlushEe = true;\n    hw::experimentSiQuery.interruptProfile = true;\n    hw::pi_intsr = 0; hw::pi_intmr = 0x40f8;\n    context.lr = 0x8024262c;', 1)
marker = '    if (argc == 3) {'
extra = '''    if (std::getenv("SHSM_FLUSH_EE_OFF")) {
        experimentFlushEe = false;
        context.msr = 0x2032;
    }
'''
body = body.replace(marker, extra + marker, 1)
marker = '        std::cout << "FLUSH_GUARDS 12\\n";'
extra = '''        const std::array<std::function<void()>, 4> eeInvalid{
            [&] { experimentFlushEe = false; }, [&] { context.lr = 0x80242630; },
            [&] { hw::pi_intsr = 8; }, [&] { context.in_callback = true; }
        };
        for (const auto& change : eeInvalid) {
            experimentFlushEe = true;
            context.lr = 0x8024262c;
            context.msr = 0xa032;
            context.hid0 = 0xc200;
            context.exceptionVector = context.flushPhase = 0;
            hw::pi_intsr = 0;
            context.in_callback = false;
            change();
            const auto before = std::array<uint64_t, 7>{context.pc, context.msr, context.hid0,
                context.srr0, context.srr1, context.flushEntries, context.flushBarriers};
            bool refused = false;
            try { experiment_flush_syscall_enter(context, 0x80212ff8); }
            catch (const std::runtime_error&) { refused = true; }
            const auto after = std::array<uint64_t, 7>{context.pc, context.msr, context.hid0,
                context.srr0, context.srr1, context.flushEntries, context.flushBarriers};
            if (!refused || before != after) { return 14; }
        }
        std::cout << "FLUSH_GUARDS 16\\n";'''
assert body.count(marker) == 1
body = body.replace(marker, extra)
body = body.replace('        context.msr = 0xa032;\n        for (unsigned offset',
    '        context.msr = std::getenv("SHSM_FLUSH_EE_OFF") ? 0x2032 : 0xa032;\n        for (unsigned offset')
host = output / 'flush-ee-host.cpp'
host.write_text('#include "finite_mem2_clear.h"\n#include "sram_frontend.h"\n#include "ipc_startup_frontend.h"\n' + prefix + body)
sources = [host, output / 'processor_adapter.cpp', output / 'ipc_reset_backend.cpp', output / 'ai_mask_backend.cpp',
    output / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
    runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'flush-ee-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(output / 'finite_mem2_clear.h'), '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    '-I', str(output), '-I', str(experiment), '-I', str(root / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources),
    *[row['object'] for row in records], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
(output / 'build.json').write_text(json.dumps({'result': 'FLUSH_EE_NATIVE_REQUIRES_COMPARISON',
    'builderSha256': sha(Path(__file__)), 'baseBuildSha256': sha(base / 'build.json'), 'records': records,
    'executableSha256': sha(exe), 'returnCode': result.returncode,
    'sourceHashes': {str(path): sha(path) for path in sources}, 'headerHashes': {str(path): sha(path) for path in output.glob('*.h')},
    'limits': ['Two unchanged current source batches rebuilt with existing optional EE profile;123objects retained.',
        'Observed caller8024262Creplaces only fixture return; CPUsc/vector/rfi/caches remain original compiled functions.']}, indent=2) + '\n')
print(result.stdout[-500:] + result.stderr)
assert result.returncode == 0
