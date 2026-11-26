"""Check real recompiled ICFlashInvalidate with an explicit immutable-code cache contract."""
from pathlib import Path
import hashlib
import json
import subprocess

output = Path('work/private-game/static-recomp/mass-cache')
exe = output / 'openshsm-mass-boot'
result = subprocess.run([str(exe), '--cache-check'], capture_output=True, text=True, timeout=30)
(output / 'cache-check.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
rows = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines()]
expected = [[0, 0, 0x4000, 1, 1]] + [[index, 1, 0x4000, 0, 0] for index in range(1, 5)]
assert rows == expected, rows
report = {'result': 'PASS', 'records': rows, 'cases': 5,
          'scopes': ['Original recompiled four-instruction cache-invalidate handler with identical registered code.',
                     'Modified code rejected without HID0/counter mutation.', 'User-mode privileged access rejected.',
                     'Missing compiled-image metadata rejected.', 'Unverified cache-enable/control-bit changes rejected.'],
          'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'wrapperSha256': hashlib.sha256(Path('experiments/wii-static-recomp/mass_boot.cpp').read_bytes()).hexdigest(),
          'limits': ['ICFI self-clear follows Dolphin reference; image validation/generation counter are explicit PC adaptations.',
                     'No physical cache timing/data-cache/changed-code translation or complete FPR/OS bootstrap acceptance.']}
(output / 'cache-check.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:real recompiled ICFlashInvalidate and4transactional refusal cases; dynamic-code/data-cache consumers remain open')
