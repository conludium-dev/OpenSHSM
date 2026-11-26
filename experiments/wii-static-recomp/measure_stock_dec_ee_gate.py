"""Reuse corrected coarse probe with DEC gate candidate and explicit prior measurement provenance."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
prior_path = root / 'clock-scheduler-batch/verification.json'
prior = json.loads(prior_path.read_text())
assert prior['result'] == 'CURRENT_CLOCK_SCHEDULER_POLL_COARSE_BATCHES55_ADVANCING_COUNTER_MEASURED'
base = Path('experiments/wii-static-recomp/measure_stock_clock_scheduler.py')
script = base.read_text()
for before, after in [
    ("output = root / 'clock-scheduler-batch'", "output = root / 'window-dec-ee-gate'"),
    ("build_path = root / 'window-dispatch-o2/build.json'", "build_path = root / 'window-dec-ee-gate/build.json'"),
    ('DISPATCH_O2_ROUTES_CALLBACK4_SDK7_SC3_LATE18_EQUAL', 'DEC_EE_GATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL'),
    ("output / 'verification.json'", "output / 'coarse-verification.json'"),
    ('CURRENT_CLOCK_SCHEDULER_POLL_COARSE_BATCHES55_ADVANCING_COUNTER_MEASURED', 'DEC_EE_GATE_COARSE_BATCHES55_MEASURED')]:
    assert before in script
    script = script.replace(before, after)
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = root / 'window-dec-ee-gate/coarse-verification.json'
report = json.loads(report_path.read_text())
report.update(priorCoarseSha256=sha(prior_path), baseMeasurerSha256=sha(base),
    priorSummary=prior['summary'])
report['limits'].append('Prior/candidate are separate native runs; no exclusive game CPU fraction or controlled live speedup.')
report_path.write_text(json.dumps(report, indent=2) + '\n')
