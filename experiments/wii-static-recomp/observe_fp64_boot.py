"""Identify the exact FP64 refusal without relaxing the existing execution profile."""
from pathlib import Path
import hashlib
import json
import os
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-ai-clock-boot'
output = private / 'mass-fp64-boot-observer'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'boot.json').read_text())
assert json.loads((base / 'audit.json').read_text())['buildSha256'] == sha(base / 'boot.json')
for name in ('mass_boot.cpp', 'boot-wrapper.cpp', 'loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
records = []
changes = []
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] == 'output_1.cpp':
        original = Path(row['source']).read_text()
        start = original.index('void func_80005F34(')
        end = original.index('\nvoid func_', start + 1)
        def observe(match):
            address, opcode, value = (int(match[group], 16) for group in (1, 2, 3))
            assert opcode == value
            section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
            assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
            before = match[0]
            after = before.replace('experiment_fp64_transfer(ctx, ' + match[3] + ');', 'experiment_fp64_boot_observe(ctx, ' + match[3] + ', ' + hex(address) + ');')
            assert before != after
            changes.append({'address': address, 'opcode': opcode, 'before': before, 'after': after})
            return after
        block = re.sub(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n    nwii::runtime::experiment_fp64_transfer\(ctx, (0x[0-9a-f]+)\);', observe, original[start:end])
        assert changes
        source = output / row['file']
        source.write_text(original[:start] + block + original[end:])
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'fp64_boot_observer.h'), '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'),
            '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / 'compile.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-2000:]
        record.update({'source': str(source), 'sourceSha256': sha(source), 'object': str(obj), 'objectSha256': sha(obj),
            'inputSource': row['source'], 'inputSourceSha256': row['sourceSha256']})
    records.append(record)
sources = [output / 'boot-wrapper.cpp', output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp',
    experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp', runtime / 'src/core/loader.cpp',
    runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_SI_EXTERNAL_DELIVERY',
    '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(output), '-I', str(experiment),
    '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in records], '-o', str(exe)],
    capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
environment = dict(os.environ)
environment.pop('SHSM_SI_IDLE_REPLAY', None)
environment.pop('SHSM_AI_CLOCK_NO_BUS', None)
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(base / 'boot-quarantine.tsv'),
    str(private / 'sram-native/settings.bin')], env=environment, capture_output=True, text=True, timeout=30)
(output / 'boot.log').write_text(result.stdout + result.stderr)
diagnostic = re.search(r'^FP64_REFUSAL .*$', result.stdout, re.M)
assert result.returncode == 7 and not result.stderr and diagnostic
assert 'BOOT_PC_CLOCK phase=6 writes=6\n' in result.stdout
(output / 'observation.json').write_text(json.dumps({'result': 'EXACT_FP64_REFUSAL_RETAINED', 'diagnostic': diagnostic[0],
    'builderSha256': sha(Path(__file__)), 'observerSha256': sha(experiment / 'fp64_boot_observer.h'),
    'baseBootSha256': sha(base / 'boot.json'), 'records': records, 'changes': changes, 'executableSha256': sha(exe),
    'logSha256': sha(output / 'boot.log'), 'sourceHashes': {str(path): sha(path) for path in sources},
    'limits': ['Delegates original FP64 guard; no new permission, FPU exception delivery or boot advance.']}, indent=2) + '\n')
print(diagnostic[0])
