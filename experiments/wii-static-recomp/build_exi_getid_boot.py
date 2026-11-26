"""Link the verified GetID module into the existing guarded boot wrapper."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
native = private / 'exi-getid-native'
base = private / 'mass-exi-select-boot'
output = private / 'mass-exi-getid-boot'
output.mkdir(exist_ok=True)
module = private / 'mass-current'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_exi_getid_native.py')], check=True)
execution = json.loads((native / 'execution.json').read_text())
for record in execution['records']:
    assert sha(Path(record['source'])) == record['sourceSha256']
    assert sha(Path(record['object'])) == record['objectSha256']
for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h'):
    (output / name).write_bytes((base / name).read_bytes())
wrapper = output / 'boot-wrapper.cpp'
body = (base / 'boot-wrapper.cpp').read_text()
entry = '    const int result = original_boot_main(argc, argv);'
assert body.count(entry) == 1
body = body.replace(entry, '''    nwii::runtime::hw::experiment_register_exi_masks(nwii::runtime::MMIODispatcher::get());
    nwii::runtime::hw::experiment_register_getid_transfer(nwii::runtime::MMIODispatcher::get());
''' + entry)
body = body.replace(entry, entry + '''
    std::cout << "BOOT_GETID_PROFILE phase=" << nwii::runtime::hw::experimentExiTransfer.phase
              << " csr=" << std::hex << nwii::runtime::hw::experimentExiMaskState[0]
              << " pi=" << nwii::runtime::hw::pi_intsr.load() << std::dec << '\\n';''')
wrapper.write_text('#include "exi_getid_frontend.h"\n' + body)
sources = [wrapper, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
           runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp',
           runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
           '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(output), '-I', str(experiment), '-I', str(module), '-I', str(runtime / 'include'),
           '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources),
           *[row['object'] for row in execution['records']], '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'boot.log').write_text(result.stdout + result.stderr)
assert (result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout) or (result.returncode == 6 and 'BOOT_UNPROVEN_RETURN' in result.stderr)
report = {'result': 'GETID_BACKEND_BOOT_UNPROVEN_RETURN_NEEDS_INVESTIGATION' if result.returncode == 6 else 'GETID_BACKEND_BOOT_BOUNDARY_REQUIRES_AUDIT',
          'returnCode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
          'executableSha256': sha(exe), 'wrapperSha256': sha(wrapper), 'baseWrapperSha256': sha(base / 'boot-wrapper.cpp'),
          'nativeExecutionSha256': sha(native / 'execution.json'), 'nativeProofSha256': sha(native / 'comparison.json'),
          'policySha256': sha(policy), 'builderSha256': sha(Path(__file__)), 'sourceHashes': {str(path): sha(path) for path in sources}}
(output / 'boot.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout[-1200:] + result.stderr)
