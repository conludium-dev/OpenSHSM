"""Compare EE-enabled original syscall return and physical flushed bytes."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_flush_syscall_dolphin.py')
body = parent.read_text().replace('dolphin-flush-syscall', 'dolphin-flush-ee')
body = body.replace('build_flush_syscall_dolphin.py', 'build_flush_ee_dolphin.py')
body = body.replace('run_flush_syscall_dolphin.ps1', 'run_flush_ee_dolphin.ps1').replace('0x2032', '0xa032')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-flush-ee/comparison.json')
report = json.loads(path.read_text())
generation = json.loads((path.parent / 'generation.json').read_text())
assert generation['eeParentSha256'] == hashlib.sha256(Path('experiments/wii-static-recomp/build_flush_syscall_dolphin.py').read_bytes()).hexdigest()
report['result'] = 'ORIGINAL_DCFLUSH_EE16_SC_RFI_A032_PHYSICAL_VISIBILITY_PASS'
report['eeVerifierParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'].append('No pending interrupt producer injected; not proof of concurrent IRQ service or physical ordering.')
path.write_text(json.dumps(report, indent=2) + '\n')
