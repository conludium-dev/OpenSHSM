"""Verify original vector entry/handler/return using the measured address/mask profile."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_si_vector_dolphin.py')
body = parent.read_text().replace('dolphin-si-vector', 'dolphin-si-boot-profile')
body = body.replace('build_si_vector_dolphin.py', 'build_si_boot_profile_dolphin.py')
body = body.replace('run_si_vector_dolphin.ps1', 'run_si_boot_profile_dolphin.ps1')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-si-boot-profile/comparison.json')
report = json.loads(path.read_text())
report['profileVerifierParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
generation = json.loads((path.parent / 'generation.json').read_text())
assert generation['profileParentSha256'] == hashlib.sha256(Path('experiments/wii-static-recomp/build_si_vector_dolphin.py').read_bytes()).hexdigest()
report['originalBehavior'] = ['Measured maskF8/softwaremaskF7FFF7F0/context80492658 fixture:16CPU SI deliveries/vector/IRQ20/callback/context/rfi return match old oracle.']
report['limits'] += ['Prepared context contents and callback-present packets; null-callback native startup still needs comparison.']
path.write_text(json.dumps(report, indent=2) + '\n')
