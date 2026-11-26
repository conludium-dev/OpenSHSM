"""Extend the existing guarded boot with the measured SI idle access pair."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-si-xy-boot'
output = private / 'mass-si-idle-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_si_idle_dolphin.py')], check=True)
subprocess.run(['python3', str(experiment / 'audit_si_xy_boot.py')], check=True)
proof_path = private / 'si-idle-native/comparison.json'
proof = json.loads(proof_path.read_text())
assert proof['builderSha256'] == sha(experiment / 'build_si_idle_native.py')
assert proof['backendSha256'] == sha(experiment / 'si_idle_backend.h')
assert proof['frontendSha256'] == sha(experiment / 'si_idle_frontend.h')
assert proof['oracleSha256'] == sha(private / 'dolphin-si-idle/comparison.json')
assert proof['generatedSha256'] == sha(private / 'si-idle-native/si-idle-block.h')
for path, digest in proof['sourceHashes'].items():
    assert sha(Path(path)) == digest
probe = private / 'si-idle-native/si-idle-probe'
assert proof['executableSha256'] == sha(probe)
replay = subprocess.run([str(probe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
assert replay.returncode == 0 and replay.stdout + replay.stderr == (private / 'si-idle-native/native.log').read_text()
for name in ('mass_boot.cpp', 'loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
entry_before = '    nwii::runtime::ProcessorContext context;\n#else\n'
entry_after = '    nwii::runtime::ProcessorContext context;\n    if (std::getenv("SHSM_SI_IDLE_REPLAY")) {\n        context.scriptedClock = true;\n        context.clockSamples.assign(192, 0);\n    }\n#else\n'
entry_source = (output / 'mass_boot.cpp').read_text()
assert entry_source.count(entry_before) == 1
(output / 'mass_boot.cpp').write_text('#include <cstdlib>\n' + entry_source.replace(entry_before, entry_after))
metadata_path = private / 'exi-getid-native/execution.json'
metadata = json.loads(metadata_path.read_text())
for row in metadata['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
record = next(row for row in metadata['records'] if row['file'] == 'output_62.cpp')
source_input = Path(record['source'])
read_before = '    // 0x8020FC98: 80036434\n    ctx.gpr[0] = nwii::runtime::experiment_getid_read32(ctx, ctx.gpr[3] + 25652); // lwz r0, 25652(r3)\n'
write_before = '    // 0x8020FCB0: 90036434\n    nwii::runtime::experiment_getid_write32(ctx, ctx.gpr[3] + 25652, ctx.gpr[0]); // stw r0, 25652(r3)\n'
read_after = read_before.replace('experiment_getid_read32(ctx, ctx.gpr[3] + 25652)', 'experiment_si_idle_read32(ctx, ctx.gpr[3] + 25652, 0x8020fc98)')
write_after = write_before.replace('experiment_getid_write32(ctx, ctx.gpr[3] + 25652, ctx.gpr[0])', 'experiment_si_idle_write32(ctx, ctx.gpr[3] + 25652, ctx.gpr[0], 0x8020fcb0)')
text = source_input.read_text()
assert text.count(read_before) == text.count(write_before) == 1
source = output / 'output_62.cpp'
source.write_text(text.replace(read_before, read_after).replace(write_before, write_after))
obj = output / 'output_62.cpp.o'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', str(experiment / 'si_idle_frontend.h'),
    '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
wrapper = output / 'boot-wrapper.cpp'
body = (base / 'boot-wrapper.cpp').read_text().replace('#include "si_xy_frontend.h"', '#include "si_idle_frontend.h"')
entry = '    const int result = original_boot_main(argc, argv);'
assert body.count(entry) == 1
body = body.replace(entry, '    nwii::runtime::hw::experiment_register_si_idle(nwii::runtime::MMIODispatcher::get());\n' + entry)
body = body.replace(entry, entry + '\n    std::cout << "BOOT_SI_CONTROL raw=" << std::hex << nwii::runtime::hw::experimentSiControl << " written=" << nwii::runtime::hw::experimentSiControlWritten << std::dec << "\\n";')
wrapper.write_text(body)
sources = [wrapper, output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
objects = [str(obj) if row['file'] == 'output_62.cpp' else str(base / 'output_63.cpp.o') if row['file'] == 'output_63.cpp' else row['object'] for row in metadata['records']]
exe = output / 'openshsm-mass-boot'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *objects, '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout
live_result = result
(output / 'live-boot.log').write_text(result.stdout + result.stderr)
replay_environment = {**os.environ, 'SHSM_SI_IDLE_REPLAY': '1'}
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], env=replay_environment, capture_output=True, text=True, timeout=30)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout
(output / 'boot.log').write_text(result.stdout + result.stderr)
(output / 'boot.json').write_text(json.dumps({'result': 'SI_IDLE_BOOT_ADVANCE_REQUIRES_AUDIT', 'returnCode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
    'builderSha256': sha(Path(__file__)), 'executableSha256': sha(exe), 'baseBootSha256': sha(base / 'boot.json'), 'baseAuditSha256': sha(base / 'audit.json'),
    'nativeProofSha256': sha(proof_path), 'wrapperSha256': sha(wrapper), 'sourceInput': str(source_input), 'sourceInputSha256': sha(source_input),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'sourceTransforms': [{'before': read_before, 'after': read_after}, {'before': write_before, 'after': write_after}],
    'objects': {path: sha(Path(path)) for path in objects}, 'sourceHashes': {str(path): sha(path) for path in sources}, 'policySha256': sha(policy),
    'frontendSha256': sha(experiment / 'si_idle_frontend.h'), 'backendSha256': sha(experiment / 'si_idle_backend.h'),
    'entrySha256': sha(output / 'mass_boot.cpp'), 'entryBefore': entry_before, 'entryAfter': entry_after,
    'replayClock': 'Existing scriptedClock provider,192zero samples; private opt-in replay fixture, default monotonic live clock unchanged.',
    'liveReturnCode': live_result.returncode, 'liveStdout': live_result.stdout, 'liveStderr': live_result.stderr,
    'limits': proof['limits'] + ['Next guest refusal retained; no first image or complete SI/device support.']}, indent=2) + '\n')
print(result.stdout[-1600:] + result.stderr)
