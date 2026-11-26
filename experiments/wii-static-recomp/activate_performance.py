"""Enable only the independently checked reset setters in the private live policy."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-performance')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_performance_native.py')], check=True)
prior = Path('work/private-game/static-recomp/mass-timebase-active/boot-quarantine.tsv')
lines = prior.read_text().splitlines(True)
removed = [f'{address:08X}\t//_unhandled\n' for address in range(0x80210720, 0x80210780, 16)]
assert all(lines.count(line) == 1 for line in removed)
policy = output / 'boot-quarantine.tsv'
policy.write_text(''.join(line for line in lines if line not in removed))
exe = output / 'openshsm-mass-boot'
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'live-boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout, result
assert all(f'BOOT_TRACE address={address:08x}' in result.stdout for address in range(0x80210720, 0x80210780, 16))
report = {'result': 'CHECKED_RESET_LIVE_BOOT_ADVANCED_ENDPOINT_UNVERIFIED',
          'stdout': result.stdout, 'removedPolicyEntries': removed, 'policySha256': sha(policy),
          'basePolicySha256': sha(prior), 'executableSha256': sha(exe),
          'setterProofSha256': sha(output / 'comparison.json'), 'scriptSha256': sha(Path(__file__)),
          'limits': ['Only six reset setters activated; other performance context/alias/read paths remain quarantined.',
                     'Live endpoint requires independent CPU/memory comparison; RTC epoch/counting/interrupts/menu/game remain unverified.']}
(output / 'live-boot.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout[-1800:], flush=True)
