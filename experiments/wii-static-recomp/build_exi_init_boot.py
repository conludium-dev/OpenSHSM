"""Extend final PI boot profile with verified EXI idle and CSR initialization."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_set_mask_pi.py'
body = builder.read_text().replace('mass-set-mask-pi', 'mass-exi-init-boot')
body = body.replace('set_mask_pi_lowering', 'exi_init_boot_lowering').replace('set_mask_pi_boot.h', 'exi_init_boot.h')
body = body.replace('verify_pi_mask_dolphin.py', 'verify_exi_init_backend.py')
body = body.replace("assert report['sites'] == 14", "assert report['sites'] == 21")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-exi-init-boot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['basePiBuilderSha256'] = sha(builder)
for name in ('set_mask_pi_boot.h', 'exi_init_backend.h'):
    report['includedHeaderHashes'][name] = sha(experiment / name)
report['baseLowererHashes']['set_mask_pi_lowering.py'] = sha(experiment / 'set_mask_pi_lowering.py')
path.write_text(json.dumps(report, indent=2) + '\n')
path = output / 'boot.json'
boot = json.loads(path.read_text())
assert boot['stdout'].count('EXI_INIT_IDLE_READ_ACCEPTED') == 3
assert boot['stdout'].count('EXI_INIT_CSR_WRITE_ACCEPTED') == 4
boot['result'] = 'GUARDED_BOOT_EXI_IDLE_CSR_INIT_ACCEPTED_NEXT_BOUNDARY_RETAINED'
boot['loweringSha256'] = sha(output / 'lowering.json')
boot['exiInitProofSha256'] = sha(Path('work/private-game/static-recomp/exi-init-backend/comparison.json'))
boot['limits'].append('Measured idle controls and four CSR-init writes only; original masking/handlers continue, device-ID/active transfers remain unverified.')
path.write_text(json.dumps(boot, indent=2) + '\n')
