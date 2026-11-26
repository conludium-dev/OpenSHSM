"""Build original-store fixture without enabling IPC reset during ordinary boot."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_branch.py'
base = Path('work/private-game/static-recomp/mass-pi-mask')
output = Path('work/private-game/static-recomp/mass-ipc-reset-fixture')
output.mkdir(exist_ok=True)
for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h'):
    (output / name).write_bytes((base / name).read_bytes())
body = builder.read_text().replace('from branch_lowering import lower', 'from ipc_reset_lowering import lower')
body = body.replace('mass-l2', 'mass-pi-mask').replace('mass-branch', 'mass-ipc-reset-fixture')
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'ipc_reset_fixture.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'ipc_reset_lowering.py')")
prefix = '#include "ipc_reset_instruction_probe.h"\n'
main = 'int main(int argc, char** argv) {'
new_main = main + '\n    if (argc == 2 && std::string(argv[1]) == "--ipc-reset-isolated") { return experiment_ipc_reset_instruction_probe(); }'
replacement = "wrapper = output / 'boot-wrapper.cpp'\nwrapper.write_text(" + repr(prefix) + " + (base / 'boot-wrapper.cpp').read_text().replace(" + repr(main) + ', ' + repr(new_main) + '))'
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", replacement)
body = body.replace("policy = base / 'boot-quarantine.tsv'", "policy = Path('work/private-game/static-recomp/mass-ni-guard/boot-quarantine.tsv')")
body = body.replace("str(wrapper), str(experiment / 'processor_adapter.cpp')", "'-I', str(output), '-I', str(upstream / 'nWiiRuntime/src/hw'), str(wrapper), str(experiment / 'processor_adapter.cpp')")
body = body.replace("str(upstream / 'nWiiRuntime/src/core/loader.cpp'),", "str(upstream / 'nWiiRuntime/src/core/loader.cpp'), str(upstream / 'nWiiRuntime/src/hw/hw_pi.cpp'), str(upstream / 'nWiiRuntime/src/hw/mmio_dispatcher.cpp'), str(experiment / 'ipc_reset_backend.cpp'),")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
assert report['sites'] == 1
report['baseBuilderSha256'] = sha(builder)
report['helperSha256'] = {name: sha(experiment / name) for name in ('ipc_reset_fixture.h', 'ipc_reset_adapter.h', 'ipc_reset_backend.h', 'ipc_reset_backend.cpp', 'ipc_reset_instruction_probe.h')}
report['privateHeaderSha256'] = {name: sha(output / name) for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h')}
report['vendorIpcSha256'] = sha(Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hw/hw_ipc.cpp'))
report['result'] = 'ORIGINAL_IPC_STORE_ISOLATED_FIXTURE_COMPILED_LIVE_REFUSAL_RETAINED'
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = sha(path)
boot['result'] = 'LIVE_IPC_MASK_UNCHANGED_REFUSAL_ISOLATED_EXECUTION_UNVERIFIED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
