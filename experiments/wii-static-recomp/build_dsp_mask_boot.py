"""Build a separate boot profile with the verified existing DSP mask backend."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
subprocess.run(['python3', str(experiment / 'verify_dsp_mask_backend.py')], check=True)
builder = experiment / 'build_ipc_reset_fixture.py'
body = builder.read_text().replace('mass-ipc-reset-fixture', 'mass-dsp-mask-boot')
body = body.replace('ipc_reset_lowering', 'dsp_mask_boot_lowering').replace('ipc_reset_fixture.h', 'dsp_mask_boot.h')
body = body.replace("assert report['sites'] == 1", "assert report['sites'] == 5")
body = body.replace("body = builder.read_text().replace(", "body = builder.read_text().replace(\"'clang++',\", \"'arch', '-arm64', 'clang++',\").replace(")
extra = '''body = body.replace("str(experiment / 'ipc_reset_backend.cpp'),", "str(experiment / 'ipc_reset_backend.cpp'), str(upstream / 'nWiiRuntime/src/hw/hw_dsp.cpp'), str(upstream / 'nWiiRuntime/src/core/event_scheduler.cpp'),")
'''
body = body.replace("exec(compile(body, str(builder), 'exec'),", extra + "exec(compile(body, str(builder), 'exec'),")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-dsp-mask-boot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['baseFixtureBuilderSha256'] = sha(builder)
report['includedHeaderHashes'] = {name: sha(experiment / name) for name in ('mi_mask_boot.h', 'mi_mask_backend.h', 'ipc_reset_boot.h', 'ipc_reset_fixture.h')}
report['baseLowererHashes'] = {name: sha(experiment / name) for name in ('mi_mask_boot_lowering.py', 'ipc_reset_boot_lowering.py', 'ipc_reset_lowering.py')}
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
report['addedVendorSourceHashes'] = {name: sha(upstream / name) for name in ('src/hw/hw_dsp.cpp', 'src/core/event_scheduler.cpp')}
path.write_text(json.dumps(report, indent=2) + '\n')
path = output / 'boot.json'
boot = json.loads(path.read_text())
for marker in ('IPC_RESET_BOOT_ACCEPTED', 'MI_MASK_BOOT_ACCEPTED', 'DSP_MASK_BOOT_READ_ACCEPTED', 'DSP_MASK_BOOT_WRITE_ACCEPTED'):
    assert boot['stdout'].count(marker) == 1
boot['result'] = 'GUARDED_BOOT_DSP_MASK_BLOCK_ACCEPTED_NEXT_BOUNDARY_RETAINED'
boot['loweringSha256'] = sha(output / 'lowering.json')
boot['dspBackendProofSha256'] = sha(Path('work/private-game/static-recomp/dsp-mask-backend/comparison.json'))
boot['limits'] = ['Original DSP mask block on explicit measured-loader0804 seed, existing vendor DSP.', 'Only verified mask accesses enabled; full DSP/audio/DMA/IRQ/game boot remains unverified.']
path.write_text(json.dumps(boot, indent=2) + '\n')
