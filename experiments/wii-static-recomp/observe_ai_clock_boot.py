"""Locate the guarded audio-clock read without accepting any new guest access."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-sram-boot'
output = private / 'mass-ai-clock-observer'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
metadata = json.loads((base / 'boot.json').read_text())
assert metadata['executableSha256'] == sha(base / 'openshsm-mass-boot')
for name in ('mass_boot.cpp', 'loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
before = '    // 0x80212AE8: 80A40180\n    ctx.gpr[5] = nwii::runtime::experiment_si_query_read32(ctx, ctx.gpr[4] + 384, 0x80212ae8); // lwz r5, 384(r4)\n'
after = before.replace('experiment_si_query_read32', 'experiment_ai_clock_observe_read32')
records = []
for row in metadata['records']:
    assert row['sourceSha256'] == sha(Path(row['source'])) and row['objectSha256'] == sha(Path(row['object']))
    record = dict(row)
    if row['file'] == 'output_63.cpp':
        text = Path(row['source']).read_text()
        assert text.count(before) == 1
        source = output / row['file']
        source.write_text(text.replace(before, after))
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'sram_frontend.h'), '-include', str(experiment / 'ai_clock_observer.h'),
            '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)],
            capture_output=True, text=True, timeout=180)
        (output / 'compile.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        record.update({'source': str(source), 'sourceSha256': sha(source), 'object': str(obj), 'objectSha256': sha(obj),
            'inputSource': row['source'], 'inputSourceSha256': row['sourceSha256']})
    records.append(record)
wrapper = output / 'boot-wrapper.cpp'
wrapper.write_bytes((base / 'boot-wrapper.cpp').read_bytes())
sources = [wrapper, output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in records], '-o', str(exe)],
    capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
settings = private / 'sram-native/settings.bin'
results = {}
for mode in ('live', 'scripted'):
    environment = dict(os.environ)
    environment.pop('SHSM_SI_IDLE_REPLAY', None)
    if mode == 'scripted':
        environment['SHSM_SI_IDLE_REPLAY'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy), str(settings)],
        env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7
    needle = '; read instruction=80212ae8 address=cd800180 length=4 physical=d800180 wimg=5 slot=1'
    assert needle in result.stdout
    if mode == 'scripted':
        assert result.stdout.replace(needle, '') == metadata['results'][mode]['stdout'] and result.stderr == metadata['results'][mode]['stderr']
    results[mode] = {'stdout': result.stdout, 'stderr': result.stderr, 'returnCode': result.returncode}
    (output / (mode + '.log')).write_text(result.stdout + result.stderr)
    print(next(line for line in result.stdout.splitlines() if line.startswith('BOOT_BOUNDARY ')))
(output / 'observation.json').write_text(json.dumps({'result': 'AI_CLOCK_READ80212AE8_CD800180_REFUSAL_OBSERVED',
    'builderSha256': sha(Path(__file__)), 'baseBootSha256': sha(base / 'boot.json'), 'executableSha256': sha(exe),
    'observerSha256': sha(experiment / 'ai_clock_observer.h'), 'records': records, 'before': before, 'after': after,
    'sourceHashes': {str(path): sha(path) for path in sources}, 'results': results,
    'limits': ['Read refusal only, no new MMIO acceptance/zero fallback/boot advance or clock behavior proof.']}, indent=2) + '\n')
print('PASS exact AI-clock read observer,2117boundary unchanged/scripted trace unchanged except diagnostic')
