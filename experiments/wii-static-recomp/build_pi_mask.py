"""Connect measured mask store to unchanged vendor PI/dispatcher in a separate module."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_branch.py'
base = Path('work/private-game/static-recomp/mass-mmio-observer')
output = Path('work/private-game/static-recomp/mass-pi-mask')
output.mkdir(exist_ok=True)
for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h'):
    (output / name).write_bytes((base / name).read_bytes())
body = builder.read_text().replace('from branch_lowering import lower', 'from pi_mask_lowering import lower')
body = body.replace('mass-l2', 'mass-mmio-observer').replace('mass-branch', 'mass-pi-mask')
body = body.replace("str(experiment / 'l2_adapter.h')", "str(experiment / 'pi_mask_adapter.h')")
body = body.replace("sha(experiment / 'branch_lowering.py')", "sha(experiment / 'pi_mask_lowering.py')")
prefix = '#include "pi_mask_probe.h"\n'
main = 'int main(int argc, char** argv) {'
new_main = main + '\n    if (argc == 2 && std::string(argv[1]) == "--pi-mask-check") { return experiment_pi_mask_probe(); }'
replacement = "wrapper = output / 'boot-wrapper.cpp'\nwrapper.write_text(" + repr(prefix) + " + (base / 'boot-wrapper.cpp').read_text().replace(" + repr(main) + ', ' + repr(new_main) + '))'
body = body.replace("wrapper = base / 'boot-wrapper.cpp'", replacement)
body = body.replace("policy = base / 'boot-quarantine.tsv'", "policy = Path('work/private-game/static-recomp/mass-ni-guard/boot-quarantine.tsv')")
body = body.replace("str(wrapper), str(experiment / 'processor_adapter.cpp')", "'-I', str(output), str(wrapper), str(experiment / 'processor_adapter.cpp')")
body = body.replace("str(upstream / 'nWiiRuntime/src/core/loader.cpp'),", "str(upstream / 'nWiiRuntime/src/core/loader.cpp'), str(upstream / 'nWiiRuntime/src/hw/hw_pi.cpp'), str(upstream / 'nWiiRuntime/src/hw/mmio_dispatcher.cpp'),")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-pi-mask')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
assert report['sites'] == 1
report['baseBuilderSha256'] = sha(builder)
report['adapterSha256'] = sha(experiment / 'pi_mask_adapter.h')
report['privateHeaderSha256'] = {name: sha(output / name) for name in ('loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h')}
report['probeSha256'] = sha(experiment / 'pi_mask_probe.h')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
report['vendorSourceSha256'] = {name: sha(upstream / name) for name in ('src/hw/hw_pi.cpp', 'src/hw/mmio_dispatcher.cpp', 'include/runtime/hw/hw.h', 'include/runtime/hw/mmio_dispatcher.h', 'include/runtime/config.h')}
report['result'] = 'EXISTING_VENDOR_PI_MASK_STORE_COMPILED_DELIVERY_UNVERIFIED'
path.write_text(json.dumps(report, indent=2) + '\n')
boot_path = output / 'boot.json'
boot = json.loads(boot_path.read_text())
boot['loweringSha256'] = sha(path)
boot['result'] = 'PI_MASK_STORE_NEXT_BOOT_ENDPOINT_UNVERIFIED'
boot_path.write_text(json.dumps(boot, indent=2) + '\n')
