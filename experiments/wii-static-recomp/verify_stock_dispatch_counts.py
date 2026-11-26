"""Verify mechanical observer-only master changes and reuse same-frame enabled observer checks."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-dispatch-counts'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
master = (output / 'fixed.cpp').read_text()
for before, after in reversed(build['masterPatches']):
    assert master.count(after) == 1
    master = master.replace(after, before)
assert master.count(build['masterHelper']) == 1
master = master.replace(build['masterHelper'], '', 1)
assert master == Path(build['masterOriginalPath']).read_text()
assert sha(Path(build['masterOriginalPath'])) == build['masterOriginalSha256']
assert '#pragma clang optimize off' in master
header = (output / 'stock_movie_timing.h').read_text()
for before, after in reversed(build['headerPatches']):
    assert header.count(after) == 1
    header = header.replace(after, before)
assert header == (root / 'window-cpu-time/stock_movie_timing.h').read_text()
base = Path('experiments/wii-static-recomp/verify_stock_cpu_time.py')
script = base.read_text()
script = script.replace("output = root / 'window-cpu-time'", "output = root / 'window-dispatch-counts'")
script = script.replace("parent_path = root / 'window-decoder-o3/build.json'", "parent_path = root / 'window-cpu-time/build.json'")
start = script.index('restored = ')
end = script.index('for unit, change', start)
script = script[:start] + script[end:]
script = script.replace('CPU_TIME_OBSERVER_FRAME_STATE_IDENTICAL3', 'DISPATCH_COUNTER_OBSERVER_FRAME_STATE_IDENTICAL3')
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
path = output / 'component-verification.json'
report = json.loads(path.read_text())
report.update(masterSourceSha256=sha(output / 'fixed.cpp'), baseVerifierSha256=sha(base),
    masterUnoptimizedStateFlowRestored=True,
    limits=report['limits'] + ['Counters affect master run_game branches only; direct frame fixture need not invoke dispatcher.',
        'Observer header and master counter additions reverse exactly to original sources; no setjmp/route/state/arithmetic change.'])
path.write_text(json.dumps(report, indent=2) + '\n')
