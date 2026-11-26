"""Audit reset proof and scoped live progress without accepting a full boot endpoint."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-performance')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_performance_native.py')], check=True)
live = json.loads((output / 'live-boot.json').read_text())
prior = Path('work/private-game/static-recomp/mass-timebase-active/boot-quarantine.tsv')
removed = [f'{address:08X}\t//_unhandled\n' for address in range(0x80210720, 0x80210780, 16)]
policy = output / 'boot-quarantine.tsv'
assert live['removedPolicyEntries'] == removed
assert live['basePolicySha256'] == sha(prior) and live['policySha256'] == sha(policy)
assert policy.read_text() == ''.join(line for line in prior.read_text().splitlines(True) if line not in removed)
assert live['scriptSha256'] == sha(experiment / 'activate_performance.py')
assert live['setterProofSha256'] == sha(output / 'comparison.json')
exe = output / 'openshsm-mass-boot'
assert live['executableSha256'] == sha(exe)
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'live-replay.log').write_text(replay.stdout + replay.stderr)
assert replay.returncode == 7 and 'BOOT_BOUNDARY pc=80210840 lr=802113e0 msr=2030' in replay.stdout
assert 'BOOT_BOUNDARY pc=80210840 lr=802113e0 msr=2030' in live['stdout']
assert all(f'BOOT_TRACE address={address:08x}' in replay.stdout for address in range(0x80210720, 0x80210780, 16))
report = {'result': 'SCOPED_PERFORMANCE_RESET_VERIFIED_LIVE_ENDPOINT_UNVERIFIED',
          'setterCases': 8, 'refusalRollbackCases': 8, 'liveNextBoundary': '0x80210840',
          'liveReportSha256': sha(output / 'live-boot.json'), 'comparisonSha256': sha(output / 'comparison.json'),
          'verifierSha256': sha(Path(__file__)),
          'limits': ['Only six zero-value boot reset setters activated; counting/interrupt/context/alias paths remain unsupported.',
                     'Live boot endpoint is not independently CPU/memory verified; RTC epoch/menu/game remain unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS bounded reset proof8cases/8guards; live boot reaches80210840, full endpoint still unverified')
