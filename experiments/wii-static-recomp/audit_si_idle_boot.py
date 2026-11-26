"""Verify the SI idle extension and exact boot replay without accepting full SI."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output, base = private / 'mass-si-idle-boot', private / 'mass-si-xy-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'audit_si_xy_boot.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_si_idle_dolphin.py')], check=True)
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
assert boot['builderSha256'] == sha(experiment / 'build_si_idle_boot.py')
assert boot['baseBootSha256'] == sha(base / 'boot.json') and boot['baseAuditSha256'] == sha(base / 'audit.json')
assert boot['frontendSha256'] == sha(experiment / 'si_idle_frontend.h')
assert boot['backendSha256'] == sha(experiment / 'si_idle_backend.h')
for path, digest in boot['sourceHashes'].items():
    assert sha(Path(path)) == digest
for path, digest in boot['objects'].items():
    assert sha(Path(path)) == digest
assert len(boot['objects']) == 125
metadata = json.loads((private / 'exi-getid-native/execution.json').read_text())
expected_objects = {str(output / 'output_62.cpp.o') if row['file'] == 'output_62.cpp' else str(base / 'output_63.cpp.o') if row['file'] == 'output_63.cpp' else row['object'] for row in metadata['records']}
assert set(boot['objects']) == expected_objects
for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
assert boot['entrySha256'] == sha(output / 'mass_boot.cpp')
assert (base / 'mass_boot.cpp').read_text().count(boot['entryBefore']) == 1
assert (output / 'mass_boot.cpp').read_text() == '#include <cstdlib>\n' + (base / 'mass_boot.cpp').read_text().replace(boot['entryBefore'], boot['entryAfter'])
body = (base / 'boot-wrapper.cpp').read_text().replace('#include "si_xy_frontend.h"', '#include "si_idle_frontend.h"')
entry = '    const int result = original_boot_main(argc, argv);'
body = body.replace(entry, '    nwii::runtime::hw::experiment_register_si_idle(nwii::runtime::MMIODispatcher::get());\n' + entry)
body = body.replace(entry, entry + '\n    std::cout << "BOOT_SI_CONTROL raw=" << std::hex << nwii::runtime::hw::experimentSiControl << " written=" << nwii::runtime::hw::experimentSiControlWritten << std::dec << "\\n";')
assert (output / 'boot-wrapper.cpp').read_text() == body
assert boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
source_input = Path(boot['sourceInput'])
assert boot['sourceInputSha256'] == sha(source_input)
source = source_input.read_text()
for change in boot['sourceTransforms']:
    assert source.count(change['before']) == 1
    source = source.replace(change['before'], change['after'])
assert (output / 'output_62.cpp').read_text() == source
assert boot['sourceSha256'] == sha(output / 'output_62.cpp') and boot['objectSha256'] == sha(output / 'output_62.cpp.o')
proof_path = private / 'si-idle-native/comparison.json'
assert boot['nativeProofSha256'] == sha(proof_path)
proof = json.loads(proof_path.read_text())
assert proof['builderSha256'] == sha(experiment / 'build_si_idle_native.py')
assert proof['backendSha256'] == boot['backendSha256'] and proof['frontendSha256'] == boot['frontendSha256']
assert proof['baseExecutionSha256'] == sha(private / 'exi-getid-native/execution.json')
assert proof['oracleSha256'] == sha(private / 'dolphin-si-idle/comparison.json')
for path, digest in proof['sourceHashes'].items():
    assert sha(Path(path)) == digest
fragment = Path(proof['sourceInput']).read_text()
assert proof['sourceInputSha256'] == sha(Path(proof['sourceInput']))
fragment = fragment[fragment.index('loc_8020FC94: ;'):fragment.index('loc_8020FCB4: ;')]
fragment = fragment.replace('experiment_getid_read32(ctx, ctx.gpr[3] + 25652)', 'experiment_si_idle_read32(ctx, ctx.gpr[3] + 25652, 0x8020fc98)')
fragment = fragment.replace('experiment_getid_write32(ctx, ctx.gpr[3] + 25652, ctx.gpr[0])', 'experiment_si_idle_write32(ctx, ctx.gpr[3] + 25652, ctx.gpr[0], 0x8020fcb0)')
assert (private / 'si-idle-native/si-idle-block.h').read_text() == 'inline void experiment_si_idle_block(nwii::runtime::CPUContext& ctx) {\n' + fragment + '}\n'
assert proof['generatedSha256'] == sha(private / 'si-idle-native/si-idle-block.h')
probe = private / 'si-idle-native/si-idle-probe'
assert proof['executableSha256'] == sha(probe)
replay = subprocess.run([str(probe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
assert replay.returncode == 0 and replay.stdout + replay.stderr == (private / 'si-idle-native/native.log').read_text()
actual = [[int(value) for value in line.split()[1:]] for line in replay.stdout.splitlines() if line.startswith('SI_IDLE_CASE ')]
oracle = json.loads((private / 'dolphin-si-idle/comparison.json').read_text())['values']
assert actual == proof['values'] == [[r['index'], r['controlBefore'], r['written'], r['controlAfter'], r['piBefore'], r['piAfter']] for r in oracle]
assert proof['guards'] == 8 and 'SI_IDLE_GUARDS 8' in replay.stdout
exe = output / 'openshsm-mass-boot'
assert boot['executableSha256'] == sha(exe)
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
assert boot['policySha256'] == sha(policy)
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], env={**os.environ, 'SHSM_SI_IDLE_REPLAY': '1'}, capture_output=True, text=True, timeout=30)
assert replay.returncode == boot['returnCode'] == 7
assert replay.stdout == boot['stdout'] and replay.stderr == boot['stderr']
assert 'BOOT_BOUNDARY pc=8020fd30 lr=8020fd30 msr=2030 calls=1972 reason=BAT MMIO/locked-cache/unmapped backing access unavailable' in replay.stdout
assert 'BOOT_SI_CONTROL raw=0 written=80000000' in replay.stdout
assert 'BOOT_GETID_PROFILE phase=6 csr=1008 pi=0' in replay.stdout
assert boot['liveReturnCode'] == 7 and 'BOOT_BOUNDARY pc=8020fd30 lr=8020fd30 msr=2030 calls=1972' in boot['liveStdout']
assert boot['liveStdout'] + boot['liveStderr'] == (output / 'live-boot.log').read_text()
live_environment = dict(os.environ)
live_environment.pop('SHSM_SI_IDLE_REPLAY', None)
live = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], env=live_environment, capture_output=True, text=True, timeout=30)
assert live.returncode == 7 and 'BOOT_BOUNDARY pc=8020fd30 lr=8020fd30 msr=2030 calls=1972' in live.stdout
assert 'BOOT_SI_CONTROL raw=0 written=80000000' in live.stdout
(output / 'audit.json').write_text(json.dumps({'result': 'SI_IDLE_BOOT1972_EXACT_REPLAY_NEXT_STATUS_GUARD', 'bootSha256': sha(boot_path),
    'auditorSha256': sha(Path(__file__)), 'nativeProofSha256': sha(proof_path), 'replayClock': boot['replayClock'],
    'next': {'retainedPC': '0x8020fd30', 'sourceInferredInstruction': '0x8020fd58', 'sourceInferredAddress': '0xcd006438', 'operation': 'read',
        'scope': 'Device transfer setup status read; source inference, no new exact-access observer.'}, 'limits': boot['limits']}, indent=2) + '\n')
print('PASS original idle16/refusals8/source125objects/exact1972-call scripted-clock replay/live boundary; SI transfer status remains refused')
