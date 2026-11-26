"""Verify original ICEnable and transactional refusals in the native immutable-code policy."""
from pathlib import Path
import hashlib
import json
import subprocess

output = Path('work/private-game/static-recomp/mass-icache')
exe = output / 'openshsm-mass-boot'
result = subprocess.run([str(exe), '--icache-check'], capture_output=True, text=True, timeout=30)
(output / 'icache-check.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines()]
expected = [[0, 0, 0x8000, 0, 1], [1, 0, 0x8000, 0, 1]]
expected += [[mode, 1, 0, 0, 0] for mode in range(2, 7)]
expected += [[7, 0, 0, 0, 0], [8, 0, 0x8000, 1, 0]]
assert rows == expected, rows
report = {'result': 'PASS', 'records': rows, 'cases': 9, 'originalIcEnableCases': 2,
          'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'scope': 'Original recompiled ICEnable plus immutable-code PC policy; Dolphin boot proof is separate.',
          'limits': ['Modified/missing/empty code images, user privilege and data-cache changes abort before HID0/counter mutation.',
                     'ICE disable/combined ICFI cases invoke the adapter directly, not an original game function.',
                     'AOT immutable-code contract, not physical instruction-cache timing or dynamic-code execution.']}
(output / 'icache-check.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:2 original ICEnable cases,5 refusals and2 direct adapter cases')
