"""Activate only the observed original HID4 function, preserving other BAT/HW gates."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-bat')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_bat.py')], check=True)
prior = Path('work/private-game/static-recomp/mass-performance/boot-quarantine.tsv')
lines = prior.read_text().splitlines(True)
removed = '80210840\t//_unhandled\n'
assert lines.count(removed) == 1
policy = output / 'boot-quarantine.tsv'
policy.write_text(''.join(line for line in lines if line != removed))
exe = output / 'openshsm-mass-boot'
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'live-boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout, result
assert 'BOOT_TRACE address=80210840' in result.stdout
report = {'result': 'BAT_HID4_SCOPED_LIVE_ADVANCE_ENDPOINT_UNVERIFIED', 'stdout': result.stdout,
          'removedPolicyEntry': removed, 'policySha256': sha(policy), 'basePolicySha256': sha(prior),
          'executableSha256': sha(exe), 'proofSha256': sha(output / 'comparison.json'), 'scriptSha256': sha(Path(__file__)),
          'limits': ['Only original HID4 function gate removed; other BAT/processor/hardware gates retained.',
                     'Live endpoint CPU/memory and post-timebase state not independently accepted.',
                     'Dolphin loader fixture BAT inputs/reference behavior; physical Wii/protection/page-table/L2-ST0/clock epoch unverified.']}
(output / 'live-boot.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout[-2200:], flush=True)
