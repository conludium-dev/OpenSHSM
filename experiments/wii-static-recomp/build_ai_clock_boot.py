"""Try the verified explicit PC clock profile in the existing SRAM boot."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import struct

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-sram-boot'
output = private / 'mass-ai-clock-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ai_clock_native.py')], check=True)
metadata_path = base / 'boot.json'
metadata = json.loads(metadata_path.read_text())
for name in ('mass_boot.cpp', 'loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
entry_path = output / 'mass_boot.cpp'
entry_before = entry_path.read_text()
entry_marker = '    context.pc = executable.entry_point;'
assert entry_before.count(entry_marker) == 1
entry_after = entry_before.replace(entry_marker,
    '    if (nwii::runtime::hw::experimentPcClock.enabled && !std::getenv("SHSM_AI_CLOCK_NO_BUS")) {\n'
    '        context.mmu.write32(0xf8, 243000000);\n'
    '    }\n' + entry_marker)
entry_path.write_text(entry_after)
records = []
for row in metadata['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] == 'output_63.cpp':
        source = output / row['file']
        text = Path(row['source']).read_text()
        start = text.index('void func_80212AC0(')
        end = text.index('\nvoid func_', start + 1)
        before = text[start:end]
        after = before.replace('experiment_si_query_read32(', 'experiment_ai_clock_read32(').replace('experiment_si_query_write32(', 'experiment_ai_clock_write32(')
        assert before != after
        source.write_text(text[:start] + after + text[end:])
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'sram_frontend.h'), '-include', str(experiment / 'ai_clock_profile.h'),
            '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / 'compile.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        record.update({'source': str(source), 'sourceSha256': sha(source), 'object': str(obj), 'objectSha256': sha(obj),
            'inputSource': row['source'], 'inputSourceSha256': row['sourceSha256'], 'before': before, 'after': after})
    records.append(record)
wrapper = output / 'boot-wrapper.cpp'
body = '#include "ai_clock_profile.h"\n' + (base / 'boot-wrapper.cpp').read_text()
body = body.replace('std::string(argv[4]) != "--no-sram"', 'std::string(argv[4]) != "--no-sram" && std::string(argv[4]) != "--no-clock"')
body = body.replace('    sram.sramAllowed = argc == 4;', '    sram.sramAllowed = argc == 4 || std::string(argv[4]) == "--no-clock";')
entry = '    const int result = original_boot_main(3, argv);'
body = body.replace(entry, '    nwii::runtime::hw::experiment_register_ipc_clock_profile(nwii::runtime::MMIODispatcher::get());\n    nwii::runtime::hw::experimentPcClock.enabled = argc == 4;\n' + entry)
body = body.replace(entry, entry + '\n    std::cout << "BOOT_PC_CLOCK phase=" << nwii::runtime::hw::experimentPcClock.phase << " writes=" << nwii::runtime::hw::experimentPcClock.writes.size() << "\\n";')
wrapper.write_text(body)
sources = [wrapper, output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in records], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
policy_input = private / 'mass-ni-guard/boot-quarantine.tsv'
policy = output / 'boot-quarantine.tsv'
tick_record = next(row for row in records if row['file'] == 'output_64.cpp')
native_metadata = json.loads((private / 'ai-clock-native/build.json').read_text())
native_tick_record = next(row for row in native_metadata['records'] if row['file'] == 'output_64.cpp')
assert tick_record['objectSha256'] == native_tick_record['objectSha256']
tick_source = Path(tick_record['source']).read_text()
tick_start = tick_source.index('void func_8021C020(')
tick_body = tick_source[tick_start:tick_source.index('\nvoid func_', tick_start + 1)]
assert tick_body.count('experiment_read_timebase(ctx)') == 1
assert '// 0x8021C020: 7C6C42E6' in tick_body and '// 0x8021C024: 4E800020' in tick_body
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
section = next(i for i in range(7) if layout[18 + i] <= 0x8021C020 and 0x8021C028 <= layout[18 + i] + layout[36 + i])
assert dol[layout[section] + 0x8021C020 - layout[18 + section]:layout[section] + 0x8021C028 - layout[18 + section]] == bytes.fromhex('7c6c42e64e800020')
policy_before = policy_input.read_text()
removed = '8021C020\tUNVERIFIED_PROCESSOR_REGISTER_268\n'
assert policy_before.count(removed) == 1
policy.write_text(policy_before.replace(removed, ''))
settings = private / 'sram-native/settings.bin'
results = {}
for mode in ('live', 'disabled', 'missing-bus'):
    environment = dict(os.environ)
    environment.pop('SHSM_SI_IDLE_REPLAY', None)
    environment.pop('SHSM_AI_CLOCK_NO_BUS', None)
    arguments = [str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy), str(settings)]
    if mode == 'disabled':
        environment['SHSM_SI_IDLE_REPLAY'] = '1'
        arguments.append('--no-clock')
    if mode == 'missing-bus':
        environment['SHSM_AI_CLOCK_NO_BUS'] = '1'
    result = subprocess.run(arguments, env=environment, capture_output=True, text=True, timeout=30)
    results[mode] = {'returnCode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    (output / (mode + '-boot.log')).write_text(result.stdout + result.stderr)
    print(mode + ': ' + result.stdout[-1800:] + result.stderr)
(output / 'boot.json').write_text(json.dumps({'result': 'PC_CLOCK_BOOT_REQUIRES_BOUNDARY_AUDIT', 'results': results,
    'builderSha256': sha(Path(__file__)), 'baseBootSha256': sha(metadata_path), 'nativeProofSha256': sha(private / 'ai-clock-native/comparison.json'),
    'executableSha256': sha(exe), 'records': records, 'sourceHashes': {str(path): sha(path) for path in sources},
    'profileSha256': sha(experiment / 'ai_clock_profile.h'), 'settingsSha256': sha(settings), 'policySha256': sha(policy),
    'policyInput': str(policy_input), 'policyInputSha256': sha(policy_input), 'removedPolicyEntry': removed,
    'tickBodySha256': hashlib.sha256(tick_body.encode()).hexdigest(),
    'entryBeforeSha256': hashlib.sha256(entry_before.encode()).hexdigest(), 'entryAfterSha256': sha(entry_path),
    'busFrequencyAdaptation': 'Private loader fixture seeds physical0xF8=243000000 before entry; not recovered SHSM code.',
    'limits': ['Explicit PC clock adaptation, not physical PLL/audible output. Live clock has no exact trace/timing claim.',
        'Original timed loops and existing budgets remain in boot; next refusal retained.']}, indent=2) + '\n')
assert all(result['returnCode'] == 7 for result in results.values())
