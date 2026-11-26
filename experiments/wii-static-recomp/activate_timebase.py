"""Activate only the independently checked64-bit reader; preserve other quarantine entries."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
base = Path('work/private-game/static-recomp/mass-timebase')
output = Path('work/private-game/static-recomp/mass-timebase-active')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_timebase.py')], check=True)
prior = Path('work/private-game/static-recomp/mass-l2/boot-quarantine.tsv')
lines = prior.read_text().splitlines(True)
removed = '8021C000\tUNVERIFIED_PROCESSOR_REGISTER_269\n'
assert lines.count(removed) == 1
policy = output / 'boot-quarantine.tsv'
policy.write_text(''.join(line for line in lines if line != removed))
exe = base / 'openshsm-mass-boot'
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
(output / 'live-boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout, result
report = {'result': 'LIVE_TIMEBASE_OS_ENDPOINT_UNVERIFIED', 'stdout': result.stdout,
          'executableSha256': sha(exe), 'policySha256': sha(policy), 'basePolicySha256': sha(prior),
          'readerProofSha256': sha(base / 'reader-comparison.json'), 'removedPolicyEntry': removed,
          'scriptSha256': sha(Path(__file__)),
          'limits': ['PC monotonic elapsed-time clock; no physical Wii/RTC epoch/calendar acceptance.',
                     'Only original8021C00064-bit reader activated;32-bit reader/other timer/interrupt paths stay quarantined.',
                     'New live OS endpoint needs independent original-code/state comparison.']}
(output / 'live-boot.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout[-2500:], flush=True)
