"""Audit scoped SPD proof and current strict floating-point boundary."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-spd')
base = Path('work/private-game/static-recomp/mass-bat')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_spd.py')], check=True)
boot = json.loads((output / 'boot.json').read_text())
assert boot['policySha256'] == sha(base / 'boot-quarantine.tsv')
assert 'BOOT_BOUNDARY pc=80210830 lr=802113e8 msr=2030' in boot['stdout']
exe = output / 'openshsm-mass-boot'
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(base / 'boot-quarantine.tsv')], capture_output=True, text=True, timeout=30)
(output / 'live-replay.log').write_text(replay.stdout + replay.stderr)
assert replay.returncode == 7 and 'BOOT_BOUNDARY pc=80210830 lr=802113e8 msr=2030' in replay.stdout
assert 'BOOT_CACHE hid0=c200' in replay.stdout
report = {'result': 'SCOPED_SPD_VERIFIED_NEW_FPSCR_ENDPOINT_UNVERIFIED', 'originalCases': 8, 'refusalRollbackCases': 4,
          'liveNextBoundary': '0x80210830 original opcode0xFFA0004C FPSCR bit instruction',
          'comparisonSha256': sha(output / 'comparison.json'), 'bootSha256': sha(output / 'boot.json'),
          'verifierSha256': sha(Path(__file__)),
          'limits': ['Original SPD function matches observed CPU/register state, not speculative physical timing.',
                     'Quarantine unchanged; next FPSCR mode and complete post-timebase CPU/memory endpoint remain unverified.',
                     'Clock epoch/physical Wii/full FP behavior/OS/IOS/GX/menu/game acceptance pending.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS scopedSPD8cases/4guards; boot advances toFPSCR80210830; complete endpoint/FPmode unverified')
