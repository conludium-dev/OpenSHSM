"""Merge only the verified alternate original BAT body into the current experimental boot."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-mem2-loader-boot'
profile = private / 'memory936-native'
output = private / 'mass-memory936-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_memory936_native.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_dc_zero_native.py')], check=True)
build = json.loads((base / 'boot.json').read_text())
for name in ('mass_boot.cpp', 'boot-wrapper.cpp', 'loader-bat-seed.h', 'fp64-template-probe.h',
        'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp', 'boot-quarantine.tsv'):
    (output / name).write_bytes((base / name).read_bytes())
for name in ('memory_protection_frontend.h', 'memory-protection-bat-plan.h'):
    (output / name).write_bytes((profile / name).read_bytes())
for name in ('reset_code_frontend.h', 'dc_zero_frontend.h'):
    (output / name).write_bytes((experiment / name).read_bytes())
removed = '802181D0\t//_unhandled\n'
policy = (output / 'boot-quarantine.tsv').read_text()
assert policy.count(removed) == 1
(output / 'boot-quarantine.tsv').write_text(policy.replace(removed, ''))
records = []
start, end = 'void func_802181D0(CPUContext& ctx) {', 'void func_802182B0(CPUContext& ctx) {'
donor_path = profile / 'output_63.cpp'
donor = donor_path.read_text()
new_body = donor[donor.index(start):donor.index(end)]
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] == 'output_63.cpp':
        source = Path(row['source']).read_text()
        old_body = source[source.index(start):source.index(end)]
        merged = source.replace(old_body, new_body, 1)
        assert merged.replace(new_body, old_body, 1) == source
        path = output / row['file']
        path.write_text(merged)
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(output / 'dc_zero_frontend.h'),
            '-I', str(output), '-I', str(experiment), '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'),
            '-c', str(path), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / 'compile.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        record.update(source=str(path), sourceSha256=sha(path), object=str(obj), objectSha256=sha(obj))
    records.append(record)
sources = [output / 'boot-wrapper.cpp', output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp',
    experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp', experiment / 'dsp_startup_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp',
    runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(output / 'dc_zero_frontend.h'),
    '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in records], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
results = {}
for mode in ('live', 'disabled'):
    environment = dict(os.environ)
    for name in ('SHSM_FPU_DISABLED', 'SHSM_FLUSH_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY',
            'SHSM_DSP_DISABLED', 'SHSM_DSP_LOST_DMA', 'SHSM_DSP_LOST_MAIL', 'SHSM_MI_DISABLED', 'SHSM_MI_NO_SIZE_FIXTURE',
            'SHSM_RI_UART_DISABLED', 'SHSM_RESET_DISABLED', 'SHSM_DC_ZERO_DISABLED', 'SHSM_MEM2_LOADER_DISABLED'):
        environment.pop(name, None)
    if mode == 'disabled':
        environment['SHSM_MI_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(output / 'boot-quarantine.tsv'),
        str(private / 'sram-native/settings.bin')], env=environment, capture_output=True, text=True, timeout=30)
    log = result.stdout + result.stderr
    path = output / (mode + '-boot.log')
    path.write_text(log)
    results[mode] = {'returnCode': result.returncode, 'logSha256': sha(path)}
    print(mode + ': ' + '\n'.join(line for line in log.splitlines() if line.startswith(('BOOT_BOUNDARY ', 'BOOT_MI ', 'BOOT_DSP ', 'BOOT_FLUSH ', 'BOOT_DCZERO '))))
(output / 'boot.json').write_text(json.dumps({
    'result': 'MEMORY936_BOOT_REQUIRES_AUDIT', 'builderSha256': sha(Path(__file__)),
    'baseBootSha256': sha(base / 'boot.json'), 'profileProofSha256': sha(profile / 'comparison.json'),
    'donorSha256': sha(donor_path), 'records': records, 'removedPolicy': removed,
    'executableSha256': sha(exe), 'results': results,
    'sourceHashes': {str(path): sha(path) for path in sources + [output / 'mass_boot.cpp', output / 'boot-quarantine.tsv',
        output / 'memory_protection_frontend.h', output / 'memory-protection-bat-plan.h',
        output / 'dc_zero_frontend.h', output / 'reset_code_frontend.h']},
    'limits': ['One alternate body merged, all other current source bytes retained;124objects reused.',
        'Measured direct-DOL emulator loader profile, not original retail loader or physical Wii.'],
}, indent=2) + '\n')
