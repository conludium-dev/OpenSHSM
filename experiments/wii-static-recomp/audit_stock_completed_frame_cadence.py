"""Quantify owned host-loop cadence without equating overlapping CPU/GPU costs."""
from pathlib import Path
import hashlib
import json
import statistics

root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
output = root / 'window-completed-frame'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
phase_path = output / 'live-audit.json'
phase = json.loads(phase_path.read_text())
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
assert phase['buildSha256'] == sha(build_path)
component_path = output / 'component-verification.json'
assert phase['componentSha256'] == sha(component_path)
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['result'] == 'COMPLETED_FRAME_GL172_EVICTION1600_GPU16_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'
artifacts = Path(phase['artifactDirectory'])
assert artifacts.parent == Path('/private/tmp')
run_path = artifacts / 'headless-sc-pc-headless-windowed-completed-frame-live-result.json'
run = json.loads(run_path.read_text())
assert sha(run_path) == phase['runSha256']
assert run['terminalReturncode'] == 0 and run['deadlineReached']
assert sha(artifacts / 'headless-sc-pc-headless-windowed-completed-frame-live.log') == run['logSha256']
assert run['executableSha256'] == build['executableSha256'] == sha(build['executablePath'])
main = Path(build['changes']['main.cpp']['sourcePath'])
assert sha(main) == build['changes']['main.cpp']['sourceSha256']
main_text = main.read_text()
sleep_start = main_text.index('      host_phases.mark(7);')
sleep_end = main_text.index('      host_phases.mark(8);', sleep_start)
assert main_text[sleep_start:sleep_end].count('std::this_thread::sleep_for(std::chrono::milliseconds(16));') == 1
summary = phase['selectedLast30Seconds']
loops = summary['loops']
seconds = summary['elapsedUs'] / 1e6
copies = round(summary['gxBatchesPerSecond'] * seconds)
assert copies > 0 and abs(copies / seconds - summary['gxBatchesPerSecond']) < 1e-9
loops_per_copy = loops / copies
ms_per_copy = seconds * 1000 / copies
sleep_per_copy = summary['meanPhaseMs']['sleepNs'] * loops_per_copy
gx_per_copy = summary['meanPhaseMs']['gxNs'] * loops_per_copy
ratios = [row['loops'] / row['gx'] for row in phase['hostRows'][-summary['intervals']:] if row['gx']]
assert ratios
report = {'result': 'OWNED_COMPLETED_FRAME_THREE_HOST_LOOPS_CADENCE_AUDITED',
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), phase_path,
        build_path, component_path, run_path, main]},
    'windowSeconds': seconds, 'hostLoops': loops, 'copyBatches': copies,
    'hostLoopsPerCopy': loops_per_copy, 'intervalRatioMedian': statistics.median(ratios),
    'wallMsPerCopy': ms_per_copy, 'hostSleepMsPerCopy': sleep_per_copy,
    'gxMsPerCopy': gx_per_copy, 'sleepFraction': sleep_per_copy / ms_per_copy,
    'nominalSleepMs': 16, 'sdkRetracesPerSecond': summary['sdkRetracesPerSecond'],
    'limits': ['Copy-bearing host batches, not exact unique original frame IDs or physical Wii timing.',
        'Aggregate host stages are serial; decoder CPU work overlaps them and cannot be added as exclusive costs.',
        'A three-loop cadence and ~54ms sleep budget is a scheduling hypothesis, not proof that removing sleep is safe.',
        'Post-copy PE marker discovery/execution timestamps and same-context causality remain to be measured.']}
path = artifacts / 'completed-frame-cadence-audit.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps({key: report[key] for key in ['hostLoopsPerCopy', 'wallMsPerCopy',
    'hostSleepMsPerCopy', 'gxMsPerCopy', 'sleepFraction']}, indent=2))
