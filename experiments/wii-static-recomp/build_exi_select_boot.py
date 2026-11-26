"""Extend the existing EXI initialization boot profile through CSR selection."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_exi_init_boot.py'
body = builder.read_text().replace('mass-exi-init-boot', 'mass-exi-select-boot')
body = body.replace('exi_init_boot_lowering', 'exi_select_boot_lowering').replace('exi_init_boot.h', 'exi_select_boot.h')
body = body.replace('verify_exi_init_backend.py', 'verify_exi_select_backend.py')
body = body.replace("assert report['sites'] == 21", "assert report['sites'] == 23")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-exi-select-boot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['baseInitBuilderSha256'] = sha(builder)
for name in ('exi_init_boot.h', 'exi_select_backend.h'):
    report['includedHeaderHashes'][name] = sha(experiment / name)
report['baseLowererHashes']['exi_init_boot_lowering.py'] = sha(experiment / 'exi_init_boot_lowering.py')
path.write_text(json.dumps(report, indent=2) + '\n')
path = output / 'boot.json'
boot = json.loads(path.read_text())
assert boot['stdout'].count('EXI_SELECT_BOOT_READ_ACCEPTED') == boot['stdout'].count('EXI_SELECT_BOOT_WRITE_ACCEPTED') == 1
boot['result'] = 'GUARDED_BOOT_EXI_CSR_SELECT_ACCEPTED_NEXT_BOUNDARY_RETAINED'
boot['loweringSha256'] = sha(output / 'lowering.json')
boot['exiSelectProofSha256'] = sha(Path('work/private-game/static-recomp/exi-select-backend/comparison.json'))
boot['limits'].append('One channel0/device2/clock0 selection pair; full EXI selection and transfers/device-ID responses remain unverified.')
path.write_text(json.dumps(boot, indent=2) + '\n')
