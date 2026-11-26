"""Reuse the separate boot builder for the final PI mask and caller checks."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
subprocess.run(['python3', str(experiment / 'verify_pi_mask_dolphin.py')], check=True)
old_pi = subprocess.run(['work/private-game/static-recomp/mass-pi-mask/openshsm-mass-boot', '--pi-mask-check'], capture_output=True, text=True, timeout=30)
assert old_pi.returncode == 0 and 'PI_MASK_GUARDS 7' in old_pi.stdout
builder = experiment / 'build_dsp_mask_boot.py'
body = builder.read_text().replace('mass-dsp-mask-boot', 'mass-set-mask-pi')
body = body.replace('dsp_mask_boot_lowering', 'set_mask_pi_lowering').replace('dsp_mask_boot.h', 'set_mask_pi_boot.h')
body = body.replace('verify_dsp_mask_backend.py', 'verify_pi_mask_dolphin.py')
body = body.replace("assert report['sites'] == 5", "assert report['sites'] == 14")
body = body.replace("str(upstream / 'nWiiRuntime/src/core/event_scheduler.cpp'),", "str(upstream / 'nWiiRuntime/src/core/event_scheduler.cpp'), str(experiment / 'ai_mask_backend.cpp'),")
old_prefix = 'prefix = \'#include "ipc_reset_instruction_probe.h"\\n\''
new_prefix = 'prefix = \'#include "ipc_reset_instruction_probe.h"\\n#include "set_mask_pi_probe.h"\\n\''
new_branch = '\n    if (argc == 2 && std::string(argv[1]) == "--set-mask-pi-check") { return experiment_set_mask_pi_probe(); }'
insertion = 'body = body.replace(' + repr(old_prefix) + ', ' + repr(new_prefix) + ')\n'
insertion += 'body = body.replace("new_main = main + ", "new_main = main + " + ' + repr(repr(new_branch) + ' + ') + ')\n'
body = body.replace("\nexec(compile(body, str(builder), 'exec'),", "\n" + insertion + "exec(compile(body, str(builder), 'exec'),")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-set-mask-pi')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['baseDspBuilderSha256'] = sha(builder)
for name in ('dsp_mask_boot.h', 'ai_mask_boot.h', 'exi_mask_boot.h', 'mi_mask_boot.h', 'ai_mask_backend.h', 'ai_mask_backend.cpp', 'exi_mask_backend.h', 'set_mask_pi_probe.h'):
    report['includedHeaderHashes'][name] = sha(experiment / name)
for name in ('dsp_mask_boot_lowering.py', 'ai_mask_boot_lowering.py', 'exi_mask_boot_lowering.py'):
    report['baseLowererHashes'][name] = sha(experiment / name)
report['addedVendorSourceHashes']['src/hw/hw_ai.cpp'] = sha(Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hw/hw_ai.cpp'))
path.write_text(json.dumps(report, indent=2) + '\n')
path = output / 'boot.json'
boot = json.loads(path.read_text())
assert boot['stdout'].count('PI_FINAL_BOOT_ACCEPTED') == 1
boot['result'] = 'GUARDED_BOOT_FINAL_PI_MASK_ACCEPTED_NEXT_BOUNDARY_RETAINED'
boot['loweringSha256'] = sha(output / 'lowering.json')
boot['piOracleSha256'] = sha(Path('work/private-game/static-recomp/dolphin-pi-mask/comparison.json'))
boot['limits'].append('One finalF0 mask store via existing PI backend; old caller unchanged, no general interrupt delivery.')
path.write_text(json.dumps(boot, indent=2) + '\n')
probe = subprocess.run([str(output / 'openshsm-mass-boot'), '--set-mask-pi-check'], capture_output=True, text=True, timeout=30)
(output / 'pi-final-probe.log').write_text(probe.stdout + probe.stderr)
assert probe.returncode == 0 and 'PI_FINAL_GUARDS 9' in probe.stdout, probe.stderr
(output / 'pi-old-probe.log').write_text(old_pi.stdout + old_pi.stderr)
print(probe.stdout)
