"""Pin actual scheduler eligibility observations against original gate evidence."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'headless-scheduler-observe'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = output / 'build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
assert sha(output / 'OpenSHSMStockSchedulerObserve') == base['executableSha256']
assert sha(output / 'libnwiiruntime.a') == base['archiveSha256']
capture = root / 'headless-sc-pc-scheduler-eligibility-sched-scheduler.jsonl'
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert len(rows) == 24 and sum(row['idle'] for row in rows) == 16
run_path = root / 'headless-sc-pc-headless-scheduler-eligibility-result.json'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == -15 and run['deadlineReached'] and run['schedulerObserve']
assert run['executableSha256'] == base['executableSha256']
log = root / 'headless-sc-pc-headless-scheduler-eligibility.log'
assert sha(log) == run['logSha256']
decoder_entries = log.read_text(errors='replace').count('[CALL] 0x80209d80')
assert decoder_entries > 0
eligible = [row for row in rows if row['idle'] and row['runBits'] == 0x80000000
    and row['runQueues'][0:2] == [0x9135E7D8, 0x9135E7D8]]
assert eligible
assert any(thread['state2C8'] == 1 and thread['word2CC'] == 0 for row in eligible for thread in row['threads'] if thread['address'] == 0x9135E7D8)
assert any(row['currentE4'] == 0x9135E7D8 and any(thread['state2C8'] == 2 and thread['word2CC'] == 0
    for thread in row['threads'] if thread['address'] == 0x9135E7D8) for row in rows)
assert any(row['hostMs'] > eligible[0]['hostMs'] and row['currentE4'] == 0x80492658 and row['waitHead'] == 0 for row in rows)
original = output / 'original-suspend-gate.json'
ghidra = output / 'ghidra/verification.json'
assert json.loads(original.read_text())['result'] == 'ORIGINAL_SUSPEND_DECREMENT_GATE_PASS5'
assert json.loads(ghidra.read_text())['result'] == 'ORIGINAL_SCHEDULER_IDLE_AND_SUSPEND_GATE_GHIDRA_PREFIX_PASS'
(output / 'live-audit.json').write_text(json.dumps({'result': 'LIVE_SUSPENDED_WORKER_RESUME_RUN_MAIN_WAKE_OBSERVED',
    'buildSha256': sha(base_path), 'runSha256': sha(run_path), 'captureSha256': sha(capture),
    'originalGateSha256': sha(original), 'ghidraReportSha256': sha(ghidra), 'auditorSha256': sha(Path(__file__).resolve()),
    'records': len(rows), 'lastObservedHostMs': max(row['hostMs'] for row in rows), 'decoderEntries': decoder_entries,
    'eligibleWorkerHostMs': eligible[0]['hostMs'],
    'limits': ['Bounded startup snapshots,not complete lifecycle/final stall capture; no queue/state mutation.',
        'Ready-state1 alone is insufficient while suspension count is1; actual queued unsuspended worker then running and main wake observed.',
        'Prior stall not reproduced, cause unknown; decoder entry count is NOT FPS or hardware behavior proof.',
        'Original software750CL decrement gate and Ghidra111instruction prefixes cover only these specific semantics,not whole scheduler/Wii FPU.']}, indent=2) + '\n')
print('LIVE_SUSPENDED_WORKER_RESUME_RUN_MAIN_WAKE_OBSERVED', decoder_entries)
