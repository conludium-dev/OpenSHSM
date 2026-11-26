"""Link the proven startup SI profile into current boot without replacing original functions."""
from pathlib import Path
import hashlib
import json
import subprocess

parent = Path('experiments/wii-static-recomp/observe_interrupt_enable_boot.py')
body = parent.read_text().replace('mass-interrupt-enable-observer', 'mass-si-queue-boot')
marker = "build = json.loads((base / 'boot.json').read_text())"
assert body.count(marker) == 1
body = body.replace(marker, marker + '''
subprocess.run(['python3', str(experiment / 'verify_si_queue_native.py')], check=True)
for path in (private / 'si-queue-native').glob('*.h'):
    (output / path.name).write_bytes(path.read_bytes())
for name in ('processor_adapter.cpp', 'ipc_reset_backend.cpp', 'ai_mask_backend.cpp', 'dsp_startup_backend.cpp'):
    (output / name).write_bytes((experiment / name).read_bytes())
''')
for name in ('processor_adapter.cpp', 'ipc_reset_backend.cpp', 'ai_mask_backend.cpp', 'dsp_startup_backend.cpp'):
    body = body.replace("experiment / '" + name + "'", "output / '" + name + "'")
    body = body.replace("(output / name).write_bytes((output / name).read_bytes())", "(output / name).write_bytes((experiment / name).read_bytes())")
body = body.replace('INTERRUPT_ENABLE_OBSERVER_REQUIRES_AUDIT', 'SI_QUEUE_BOOT_REQUIRES_AUDIT')
body = body.replace("'BOOT_FINITE_MEM2 ')", "'BOOT_FINITE_MEM2 ', 'BOOT_SI_DELIVERY ', 'BOOT_SI_CONTROL ')")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-si-queue-boot/build.json')
report = json.loads(path.read_text())
profile = Path('work/private-game/static-recomp/si-queue-native/comparison.json')
report['queueProofSha256'] = hashlib.sha256(profile.read_bytes()).hexdigest()
report['headerHashes'] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in path.parent.glob('*.h')}
report['limits'] = ['Exact observed maskF8/context80492658/softwaremaskF7FFF7F0 only; no other producer permission.',
    'Current125objects/originalcontext/queue left intact; no context overwrite/IRQclear/handler substitution.']
path.write_text(json.dumps(report, indent=2) + '\n')
