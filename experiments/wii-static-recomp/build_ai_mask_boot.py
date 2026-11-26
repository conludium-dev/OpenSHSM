"""Extend the existing separate DSP boot profile with verified Wii AI masks."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_dsp_mask_boot.py'
body = builder.read_text().replace('mass-dsp-mask-boot', 'mass-ai-mask-boot')
body = body.replace('dsp_mask_boot_lowering', 'ai_mask_boot_lowering').replace('dsp_mask_boot.h', 'ai_mask_boot.h')
body = body.replace('verify_dsp_mask_backend.py', 'verify_ai_mask_backend.py')
body = body.replace("assert report['sites'] == 5", "assert report['sites'] == 7")
body = body.replace("str(upstream / 'nWiiRuntime/src/core/event_scheduler.cpp'),", "str(upstream / 'nWiiRuntime/src/core/event_scheduler.cpp'), str(experiment / 'ai_mask_backend.cpp'),")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-ai-mask-boot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['baseDspBuilderSha256'] = sha(builder)
for name in ('dsp_mask_boot.h', 'ai_mask_backend.h', 'ai_mask_backend.cpp'):
    report['includedHeaderHashes'][name] = sha(experiment / name)
report['baseLowererHashes']['dsp_mask_boot_lowering.py'] = sha(experiment / 'dsp_mask_boot_lowering.py')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
report['addedVendorSourceHashes']['src/hw/hw_ai.cpp'] = sha(upstream / 'src/hw/hw_ai.cpp')
path.write_text(json.dumps(report, indent=2) + '\n')
path = output / 'boot.json'
boot = json.loads(path.read_text())
assert boot['stdout'].count('AI_MASK_BOOT_READ_ACCEPTED') == boot['stdout'].count('AI_MASK_BOOT_WRITE_ACCEPTED') == 1
boot['result'] = 'GUARDED_BOOT_WII_AI_MASK_BLOCK_ACCEPTED_NEXT_BOUNDARY_RETAINED'
boot['loweringSha256'] = sha(output / 'lowering.json')
boot['aiBackendProofSha256'] = sha(Path('work/private-game/static-recomp/ai-mask-backend/comparison.json'))
boot['limits'].append('Wii AI alias/quiescent mask projection with explicit42 loader seed; no playback or active AI IRQs.')
path.write_text(json.dumps(boot, indent=2) + '\n')
