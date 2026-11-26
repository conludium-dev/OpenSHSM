"""Keep the cache gap explicit while preserving earlier immutable-ICE and release evidence."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-coherence-probe')
subprocess.run(['python3', str(experiment / 'verify_coherence.py')], check=True)
subprocess.run(['python3', str(experiment / 'audit_icache.py')], check=True)
comparison = json.loads((output / 'comparison.json').read_text())
assert comparison['result'] == 'KNOWN_CACHE_GAP_CONFIRMED'
assert comparison['nativeFailsAccurateDolphinAtSamples'] == [1, 3]
report = {'result': 'CACHE_IMPLEMENTATION_REQUIRED', 'gapVerified': True, 'dceNativeAccepted': False,
          'comparisonSha256': hashlib.sha256((output / 'comparison.json').read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'releaseUnchanged': True, 'limits': comparison['limits'], 'next': comparison['next']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('Audit preserved: cache gap is a required implementation step, not a passing game/cache gate')
