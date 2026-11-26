"""Apply the enabled nonlocal/SDK/SC/late-frame gates to the calibrated WALL observer."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
output = root / 'window-callback-wall-profile'
build = json.loads((output / 'build.json').read_text())
proof_path = root / 'callback-wall-clock/verification.json'
proof = json.loads(proof_path.read_text())
assert sha(proof_path) == build['wallClockProofSha256']
assert build['sampleClock'] == 'CLOCK_MONOTONIC_RAW' and build['counterOrder'][7] == 'sampleWallNs'
helper = Path(build['iosSourcePath']).parent / 'stock_callback_profile.h'
assert sha(helper) == proof['helperSha256']
assert helper.read_text().replace('CLOCK_MONOTONIC_RAW', 'CLOCK_THREAD_CPUTIME_ID', 1) == Path(proof['originalHelperPath']).read_text()
base = Path('experiments/wii-static-recomp/verify_stock_callback_o2_profile.py')
script = base.read_text().replace('window-callback-o2-profile', 'window-callback-wall-profile').replace(
    'CURRENT_CALLBACK_O2_PROFILE_NONLOCAL4_SDK7_SC3_LATE18_EQUAL',
    'CURRENT_CALLBACK_WALL_PROFILE_NONLOCAL4_SDK7_SC3_LATE18_EQUAL')
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
report.update(wallClockProofSha256=sha(proof_path), baseWallVerifierSha256=sha(base), sampleClock='CLOCK_MONOTONIC_RAW')
report['limits'].append('WALL includes host preemption, not threadCPU; original public CPU helper and guest clocks unchanged.')
report_path.write_text(json.dumps(report, indent=2) + '\n')
