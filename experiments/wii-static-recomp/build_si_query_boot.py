"""Enable the verified shared SI packet profile in the existing guarded boot."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-si-idle-boot'
output = private / 'mass-si-query-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_si_vector_native.py')], check=True)
metadata_path = private / 'si-vector-native/build.json'
metadata = json.loads(metadata_path.read_text())
base_report = json.loads((base / 'boot.json').read_text())
assert base_report['executableSha256'] == sha(base / 'openshsm-mass-boot')
for name in ('mass_boot.cpp', 'loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
records = []
for row in metadata['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] in ('output_62.cpp', 'output_63.cpp'):
        text = Path(row['source']).read_text()
        transforms = []
        if row['file'] == 'output_62.cpp':
            for instruction, old, new in [(0x8020fc98, 'experiment_si_query_read32', 'experiment_si_idle_read32'),
                    (0x8020fcb0, 'experiment_si_query_write32', 'experiment_si_idle_write32')]:
                line = next(line for line in text.splitlines(True) if hex(instruction) in line and old + '(' in line)
                assert text.count(line) == 1
                transforms.append({'before': line, 'after': line.replace(old, new)})
        else:
            before = '    ctx.gpr[4] = nwii::runtime::bat_memory_read16(ctx, ctx.gpr[3] + 8300); // lhz\n'
            after = '    ctx.gpr[4] = nwii::runtime::experiment_uart_next_read16(ctx, ctx.gpr[3] + 8300, 0x80210620); // lhz\n'
            assert text.count(before) == 2
            transforms.append({'before': before, 'after': after})
            line = next(line for line in text.splitlines(True) if '0x8020feec' in line and 'experiment_si_query_write32(' in line)
            assert text.count(line) == 1
            transforms.append({'before': line, 'after': line.replace('experiment_si_query_write32', 'experiment_si_xy_write32')})
        for transform in transforms:
            text = text.replace(transform['before'], transform['after'])
        source = output / row['file']
        source.write_text(text)
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'si_query_frontend.h'), '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'),
            '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / (row['file'] + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        record.update({'source': str(source), 'sourceSha256': sha(source), 'object': str(obj), 'objectSha256': sha(obj),
            'inputSource': row['source'], 'inputSourceSha256': row['sourceSha256'], 'transforms': transforms})
    records.append(record)
wrapper = output / 'boot-wrapper.cpp'
body = (base / 'boot-wrapper.cpp').read_text().replace('#include "si_idle_frontend.h"', '#include "si_query_frontend.h"')
registration = '    nwii::runtime::hw::experiment_register_si_idle(nwii::runtime::MMIODispatcher::get());'
assert body.count(registration) == 1
body = body.replace(registration, '    nwii::runtime::hw::experiment_register_si_query(nwii::runtime::MMIODispatcher::get());\n    nwii::runtime::hw::experimentSiQuery.interruptProfile = true;')
entry = '    const int result = original_boot_main(argc, argv);'
assert body.count(entry) == 1
body = body.replace(entry, entry + '\n    std::cout << "BOOT_SI_DELIVERY entries=" << nwii::runtime::siExternalEntries << " callbacks=" << nwii::runtime::hw::experimentSiQuery.callbackCount << "\\n";')
wrapper.write_text(body)
sources = [wrapper, output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in records], '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
results = {}
for mode in ('live', 'scripted'):
    environment = dict(os.environ)
    environment.pop('SHSM_SI_IDLE_REPLAY', None)
    if mode == 'scripted':
        environment['SHSM_SI_IDLE_REPLAY'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], env=environment,
        capture_output=True, text=True, timeout=30)
    (output / (mode + '-boot.log')).write_text(result.stdout + result.stderr)
    results[mode] = {'returnCode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    print(mode + ': ' + result.stdout[-1500:] + result.stderr)
(output / 'boot.json').write_text(json.dumps({'result': 'SI_QUERY_BOOT_REQUIRES_BOUNDARY_AUDIT', 'results': results,
    'builderSha256': sha(Path(__file__)), 'nativeBuildSha256': sha(metadata_path), 'nativeProofSha256': sha(private / 'si-vector-native/comparison.json'),
    'baseBootSha256': sha(base / 'boot.json'), 'executableSha256': sha(exe), 'records': records,
    'sourceHashes': {str(path): sha(path) for path in sources}, 'policySha256': sha(policy),
    'frontendSha256': sha(experiment / 'si_query_frontend.h'), 'pollSha256': sha(experiment / 'boot_poll.h'),
    'externalSha256': sha(experiment / 'si_external_delivery.h'), 'batMemorySha256': sha(experiment / 'bat_memory_frontend.h'),
    'limits': ['Existing guarded boot, not a game-launch claim. Only measured disconnected SI profile enabled; next refusal preserved.',
        'Prepared vector-context compatibility gate remains strict; live and scripted traces are distinct.']}, indent=2) + '\n')
assert all(result['returnCode'] == 7 and 'BOOT_BOUNDARY' in result['stdout'] for result in results.values())
