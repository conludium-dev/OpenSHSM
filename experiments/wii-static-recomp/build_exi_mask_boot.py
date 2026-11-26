"""Extend separate AI boot profile with measured EXI mask blocks."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_ai_mask_boot.py'
body = builder.read_text().replace('mass-ai-mask-boot', 'mass-exi-mask-boot')
body = body.replace('ai_mask_boot_lowering', 'exi_mask_boot_lowering').replace('ai_mask_boot.h', 'exi_mask_boot.h')
body = body.replace('verify_ai_mask_backend.py', 'verify_exi_mask_backend.py')
body = body.replace("assert report['sites'] == 7", "assert report['sites'] == 13")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-exi-mask-boot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['baseAiBuilderSha256'] = sha(builder)
for name in ('ai_mask_boot.h', 'exi_mask_backend.h'):
    report['includedHeaderHashes'][name] = sha(experiment / name)
report['baseLowererHashes']['ai_mask_boot_lowering.py'] = sha(experiment / 'ai_mask_boot_lowering.py')
path.write_text(json.dumps(report, indent=2) + '\n')
path = output / 'boot.json'
boot = json.loads(path.read_text())
assert boot['stdout'].count('EXI_MASK_BOOT_READ_ACCEPTED') == boot['stdout'].count('EXI_MASK_BOOT_WRITE_ACCEPTED') == 3
boot['result'] = 'GUARDED_BOOT_THREE_EXI_MASK_BLOCKS_ACCEPTED_NEXT_BOUNDARY_RETAINED'
boot['loweringSha256'] = sha(output / 'lowering.json')
boot['exiBackendProofSha256'] = sha(Path('work/private-game/static-recomp/exi-mask-backend/comparison.json'))
boot['limits'].append('Three fixed measured loader EXI channel profiles and disabled-mask boot path only; no transfers/acknowledgements/device protocols or automatic IRQ delivery.')
path.write_text(json.dumps(boot, indent=2) + '\n')
