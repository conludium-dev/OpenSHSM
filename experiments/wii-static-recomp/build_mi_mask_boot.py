"""Advance only the measured MI mask write in the existing boot experiment."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
subprocess.run(['python3', str(experiment / 'verify_mi_mask_backend.py')], check=True)
builder = experiment / 'build_ipc_reset_boot.py'
body = builder.read_text().replace('mass-ipc-reset-boot', 'mass-mi-mask-boot')
body = body.replace('ipc_reset_boot_lowering', 'mi_mask_boot_lowering').replace('ipc_reset_boot.h', 'mi_mask_boot.h')
body = body.replace("assert report['sites'] == 2", "assert report['sites'] == 3")
body = body.replace('memory instruction=802176e4 address=cc00401c value=0 length=2 physical=c00401c wimg=5 slot=1',
                    'memory instruction=802176f4 address=cc00500a length=2 read physical=c00500a wimg=5 slot=1')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-mi-mask-boot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['baseBootBuilderSha256'] = sha(builder)
report['includedHeaderHashes'] = {name: sha(experiment / name) for name in ('mi_mask_backend.h', 'ipc_reset_boot.h')}
report['baseBootLowererSha256'] = sha(experiment / 'ipc_reset_boot_lowering.py')
path.write_text(json.dumps(report, indent=2) + '\n')
path = output / 'boot.json'
boot = json.loads(path.read_text())
assert boot['stdout'].count('MI_MASK_BOOT_ACCEPTED instruction=802176e4') == 1
boot['result'] = 'GUARDED_BOOT_MI_MASK_ACCEPTED_NEXT_DSP_READ_REFUSED'
boot['loweringSha256'] = sha(output / 'lowering.json')
boot['miBackendProofSha256'] = sha(Path('work/private-game/static-recomp/mi-mask-backend/comparison.json'))
boot['limits'] = ['Only original zero-MI-mask store enabled with reset-only PI/EE0/BAT/no-pending-event guards.', 'Next DSP read remains refused; no protection faults, general MI/DSP/IRQ or full boot acceptance.']
path.write_text(json.dumps(boot, indent=2) + '\n')
