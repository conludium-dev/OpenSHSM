"""Try the verified first-use FPU exception path in the existing clock boot."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-ai-clock-boot'
output = private / 'mass-fpu-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_fpu_first_use_native.py')], check=True)
build = json.loads((base / 'boot.json').read_text())
native = json.loads((private / 'fpu-first-use-native/build.json').read_text())
for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
entry_before = (base / 'mass_boot.cpp').read_text()
entry_marker = '    nwii::runtime::experiment_sram_attach_memory(context);'
assert entry_before.count(entry_marker) == 1
entry_after = entry_before.replace(entry_marker, entry_marker + '\n    context.fpuFirstUse = !std::getenv("SHSM_FPU_DISABLED");')
diagnostic_marker = '        std::cout << "BOOT_REGISTERS";'
assert entry_after.count(diagnostic_marker) == 1
entry_after = entry_after.replace(diagnostic_marker, '        std::cout << "BOOT_FPU entries=" << context.fpuEntries << " vector=" << context.exceptionVector << " resume=" << std::hex << context.fpuResume << std::dec << "\\n";\n' + diagnostic_marker)
(output / 'mass_boot.cpp').write_text(entry_after)
wrapper = output / 'boot-wrapper.cpp'
wrapper_body = '#include "fpu_first_use.h"\n' + (base / 'boot-wrapper.cpp').read_text()
stack_marker = '    if (context.gpr[1] >= 16 && context.mmu.get_ptr(context.gpr[1] - 16)) {'
assert wrapper_body.count(stack_marker) == 1
wrapper_body = wrapper_body.replace(stack_marker, '    if ((context.msr & 0x10) && context.gpr[1] >= 16 && context.mmu.get_ptr(context.gpr[1] - 16)) {')
wrapper.write_text(wrapper_body)
records = native['records']
assert len(records) == 125
for row in records:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
sources = [wrapper, output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER',
    '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'),
    '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in records], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
policy_input = base / 'boot-quarantine.tsv'
policy = output / 'boot-quarantine.tsv'
removed_policy_entry = '80211BA0\t//_unhandled\n'
policy_text = policy_input.read_text()
assert policy_text.count(removed_policy_entry) == 1
policy.write_text(policy_text.replace(removed_policy_entry, ''))
results = {}
for mode in ('live', 'disabled'):
    environment = dict(os.environ)
    for name in ('SHSM_FPU_DISABLED', 'SHSM_AI_CLOCK_NO_BUS', 'SHSM_SI_IDLE_REPLAY'):
        environment.pop(name, None)
    if mode == 'disabled':
        environment['SHSM_FPU_DISABLED'] = '1'
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy),
        str(private / 'sram-native/settings.bin')], env=environment, capture_output=True, text=True, timeout=30)
    (output / (mode + '-boot.log')).write_text(result.stdout + result.stderr)
    results[mode] = {'returnCode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    print(mode + ':\n' + '\n'.join(line for line in result.stdout.splitlines() if line.startswith(('BOOT_BOUNDARY ', 'BOOT_FPU ', 'BOOT_PC_CLOCK '))) + result.stderr)
(output / 'boot.json').write_text(json.dumps({'result': 'FPU_BOOT_REQUIRES_BOUNDARY_AUDIT', 'builderSha256': sha(Path(__file__)),
    'baseBootSha256': sha(base / 'boot.json'), 'nativeBuildSha256': sha(private / 'fpu-first-use-native/build.json'),
    'nativeProofSha256': sha(private / 'fpu-first-use-native/comparison.json'), 'records': records,
    'sourceHashes': {str(path): sha(path) for path in sources}, 'entryBeforeSha256': hashlib.sha256(entry_before.encode()).hexdigest(),
    'entryAfterSha256': sha(output / 'mass_boot.cpp'), 'executableSha256': sha(exe), 'results': results,
    'policyInputSha256': sha(policy_input), 'policySha256': sha(policy), 'removedPolicyEntry': removed_policy_entry,
    'headerHashes': native['headerHashes'], 'limits': ['Only measured first-use owner0/empty context; original vector/handler/rfi/lfd execute.',
        'Native exception800 maps to compiled vector template; no populated restoration/physical timing/first frame claim.']}, indent=2) + '\n')
assert all(row['returnCode'] == 7 for row in results.values())
