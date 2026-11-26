"""Remove only the verified original NI setter gate after whole-module guard audit."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-ni-guard')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'audit_ni_guard.py')], check=True)
prior = Path('work/private-game/static-recomp/mass-bat/boot-quarantine.tsv')
removed = '80210830\t//_mtfsb1/mtfsb0_stub_(FPSCR_ignored\n'
lines = prior.read_text().splitlines(True)
assert lines.count(removed) == 1
policy = output / 'boot-quarantine.tsv'
policy.write_text(''.join(line for line in lines if line != removed))
exe = output / 'openshsm-mass-boot'
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
(output / 'live-boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_TRACE address=80210830' in result.stdout and 'BOOT_BOUNDARY' in result.stdout
assert 'BOOT_BOUNDARY pc=80210830 ' not in result.stdout
report = {'result': 'NI_SCOPED_SETTER_ACTIVATED_WITH_STRICT_FP_GUARDS_ENDPOINT_UNVERIFIED', 'stdout': result.stdout,
          'removedPolicyEntry': removed, 'basePolicySha256': sha(prior), 'policySha256': sha(policy),
          'executableSha256': sha(exe), 'proofSha256': sha(output / 'audit.json'), 'scriptSha256': sha(Path(__file__)),
          'limits': ['Only original NI setter gate removed; all other function/service gates retained.',
                     'NI-sensitive unverified FP operations trap before effects, not successful approximations.',
                     'Complete post-clock/new live CPU-memory endpoint and original menu/game remain unverified.']}
(output / 'live-boot.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout[-2400:], flush=True)
