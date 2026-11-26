"""Reuse the current optimized profile pipeline with the calibrated private WALL clock helper only."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
proof_path = root / 'callback-wall-clock/verification.json'
proof = json.loads(proof_path.read_text())
assert proof['result'] == 'WALL_CLOCK_ONLY_HELPER_NONLOCAL_COMPONENT_CALIBRATION5_PASS'
assert sha(Path(proof['helperPath'])) == proof['helperSha256']
assert sha(Path(proof['originalHelperPath'])) == proof['originalHelperSha256']
base = Path('experiments/wii-static-recomp/build_stock_callback_o2_profile.py')
script = base.read_text()
patches = [
    ("output = root / 'window-callback-o2-profile'", "output = root / 'window-callback-wall-profile'"),
    ("prefix='openshsm-callback-o2-'", "prefix='openshsm-callback-wall-'"),
    ("source.write_bytes(prepared_source.read_bytes())", """source.write_bytes(prepared_source.read_bytes())
(cache / 'stock_callback_profile.h').write_bytes(Path(proof['helperPath']).read_bytes())"""),
    ('OpenSHSMStockCallbackO2Profile', 'OpenSHSMStockCallbackWallProfile'),
    ('CURRENT_IOS_O2_LATE_CALLBACK_PROFILE_BUILT_UNVERIFIED', 'CURRENT_IOS_O2_LATE_CALLBACK_WALL_PROFILE_BUILT_UNVERIFIED')]
for before, after in patches:
    assert before in script
    script = script.replace(before, after)
scope = {'__file__': __file__, 'proof': proof}
exec(compile(script, str(base), 'exec'), scope)
output = root / 'window-callback-wall-profile'
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
helper = Path(build['iosSourcePath']).parent / 'stock_callback_profile.h'
assert sha(helper) == proof['helperSha256']
build.update(sampleClock=proof['clock'], counterOrder=proof['counterOrder'],
    wallClockProofSha256=sha(proof_path), baseBuilderSha256=sha(base))
build['dependencies'][str(helper)] = sha(helper)
build['limits'].extend(['ONLY diagnostic clock changed to calibrated monotonic WALL; native guest clocks/IRQ/timebase unchanged.',
    'Internal legacy helper function name cpu_ns does not imply CPU measurement; counterOrder explicitly sampleWallNs.'])
build_path.write_text(json.dumps(build, indent=2) + '\n')
