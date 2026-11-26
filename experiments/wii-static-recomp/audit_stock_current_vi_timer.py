"""Correlate current timer-only native VI with original SDK counters and exact late owned packets."""
from pathlib import Path
import argparse
import hashlib
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
args = parser.parse_args()
artifacts = args.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp') and re.fullmatch(r'openshsm-run-[A-Za-z0-9_-]+', artifacts.name)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-current-vi-timer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
run_path = artifacts / 'headless-sc-pc-headless-windowed-current-vi-timer-result.json'
run = json.loads(run_path.read_text())
assert run['temporaryEvidence'] and Path(run['artifactDirectory']).resolve() == artifacts
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'CURRENT_TIMER_MAIN_ONLY_LINK_SOURCE_SDK_MARKERS_VERIFIED'
assert component['buildSha256'] == sha(output / 'build.json')

phase_base = Path('experiments/wii-static-recomp/audit_stock_live_phases.py')
script = phase_base.read_text()
start = script.index('parser = argparse.ArgumentParser()')
end = script.index("output = root /", start)
script = script[:start] + "args = type('PhaseOptions', (), {'timer_only': True})()\n" + script[end:]
start = script.index('if args.timer_only:\n')
end = script.index('vi_original = Path(vi_build', start)
script = script[:start] + """vi_build = json.loads((root / 'window-live-phases/build.json').read_text())
vi_source = root / 'window-live-phases/output_39.cpp'
""" + script[end:]
for before, after in [
    ("output = root / ('window-vi-timer' if args.timer_only else 'window-live-phases')", "output = root / 'window-current-vi-timer'"),
    ("tag = 'vi-timer' if args.timer_only else 'live-phases'", "tag = 'current-vi-timer'"),
    ("exe = output / ('OpenSHSMStockVITimer' if args.timer_only else 'OpenSHSMStockLivePhases')", "exe = Path(build['executablePath'])"),
    ("root / f'headless-sc-pc-", "artifacts / f'headless-sc-pc-"),
    ("root.glob(f'headless-sc-pc-{tag}-efb_debug_*.bmp')", "Path(run['capturePrefix']).parent.glob(Path(run['capturePrefix']).name + '_debug_*.bmp')")]:
    assert before in script
    script = script.replace(before, after)
exec(compile(script, str(phase_base), 'exec'), {'__file__': __file__, 'artifacts': artifacts})
phase_path = output / 'live-audit.json'
phase = json.loads(phase_path.read_text())
assert all(row['publications'] == 0 for row in phase['hostRows'])
phase.update(result='CURRENT_TIMER_ONLY_HOST_ORIGINAL_SDK_PHASES_AUDITED',
    componentSha256=sha(component_path), baseAuditorSha256=sha(phase_base), artifactDirectory=str(artifacts))
phase['limits'].append('Native GUI VI producer removed only; configured60Hz scheduler unchanged, not physical Wii beam/region timing proof.')
phase_path.write_text(json.dumps(phase, indent=2) + '\n')

base = Path('experiments/wii-static-recomp/audit_stock_scheduler_o2.py')
script = base.read_text()
patches = [
    ("output = root / 'window-scheduler-o2'", "output = root / 'window-current-vi-timer'"),
    ("parent_path = root / 'window-movie-late/build.json'", "parent_path = root / 'window-dec-ee-gate/build.json'"),
    ('SCHEDULER_O2_CONTRACT_CALLBACK4_SDK7_SC3_LATE18_EQUAL', 'CURRENT_TIMER_MAIN_ONLY_LINK_SOURCE_SDK_MARKERS_VERIFIED'),
    ('headless-sc-pc-headless-windowed-scheduler-o2', 'headless-sc-pc-headless-windowed-current-vi-timer'),
    ('headless-sc-pc-scheduler-o2-movie-timing.jsonl', 'headless-sc-pc-current-vi-timer-movie-timing.jsonl'),
    ('headless-sc-pc-scheduler-o2-efb', 'headless-sc-pc-current-vi-timer-efb'),
    ("prior_path = root / 'window-movie-late/live-input-audit.json'", "prior_path = root / 'window-dec-ee-gate/live-input-audit.json'"),
    ("prior['result'] == 'DELAYED_LIVE_OWNED_MOVIE_PACKETS_AUDITED'", "prior['result'] == 'DEC_EE_GATE_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED'"),
    ('SCHEDULER_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED', 'CURRENT_TIMER_ONLY_LATE_PACKET_VISUAL_AUDIO_AUDITED')]
for before, after in patches:
    assert before in script
    script = script.replace(before, after)
script = script.replace("scope = {'__file__': __file__}",
    """script = script.replace("root / 'headless-sc-pc-", "artifacts / 'headless-sc-pc-")
scope = {'__file__': __file__, 'artifacts': artifacts}""")
script = script.replace("text = (root / 'headless-sc-pc-", "text = (artifacts / 'headless-sc-pc-")
exec(compile(script, str(base), 'exec'), {'__file__': __file__, 'artifacts': artifacts})
packet_path = output / 'live-input-audit.json'
packet = json.loads(packet_path.read_text())
packet.update(phaseAuditSha256=sha(phase_path), baseCurrentAuditorSha256=sha(base), artifactDirectory=str(artifacts))
prior_path = root / 'window-dec-ee-gate/live-input-audit.json'
prior = json.loads(prior_path.read_text())
prior_artifacts = Path(prior['artifactDirectory'])
prior_run_path = prior_artifacts / 'headless-sc-pc-headless-windowed-dec-ee-gate-result.json'
assert sha(prior_run_path) == prior['runSha256']
prior_run = json.loads(prior_run_path.read_text())
prior_log = prior_artifacts / 'headless-sc-pc-headless-windowed-dec-ee-gate.log'
assert sha(prior_log) == prior_run['logSha256']
phase_source = phase_base.read_text()
phase_start = phase_source.index("fields = ['hostUs'")
phase_end = phase_source.index('movie_path = root /', phase_start)
baseline_scope = {'re': re, 'text': prior_log.read_text(),
    'args': type('PhaseOptions', (), {'timer_only': False})()}
exec(compile(phase_source[phase_start:phase_end], str(phase_base), 'exec'), baseline_scope)
def position_rates(report):
    result = {}
    for movie in report['summary']['movies']:
        group = [row for row in report['records'] if len(row['moduloPositionMatches']) == 1
            and row['moduloPositionMatches'][0]['movie'] == movie]
        elapsed = group[-1]['begin']['hostUs'] - group[0]['begin']['hostUs']
        delta = group[-1]['capture']['descriptorField4'] - group[0]['capture']['descriptorField4']
        assert elapsed > 0 and delta >= 0
        result[movie] = {'positionDelta': delta, 'elapsedUs': elapsed,
            'sourcePositionsPerWallSecond': delta * 1000000 / elapsed,
            'headerFps': report['summary']['capturedPlayback'][movie]['headerFps']}
    return result
packet.update(baselinePhaseSummary=baseline_scope['summary'], currentPhaseSummary=phase['selectedLast30Seconds'],
    positionRateComparison={'baseline': position_rates(prior), 'timerOnly': position_rates(packet)},
    baselineAuditSha256=sha(prior_path))
packet['limits'].append('Native VI publication policy changed; decoder latency cannot substitute complete gameplay/save/controller/beam acceptance.')
packet['limits'].append('Source-position advance rate is decoder input progression, not independently measured displayed playback; sustained below-header progression prevents promotion.')
packet_path.write_text(json.dumps(packet, indent=2) + '\n')
print('CURRENT_TIMER_ONLY_SDK_LATE_PACKET_COMPARISON_AUDITED')
print(json.dumps({'baselinePhase': packet['baselinePhaseSummary'],
    'positionRateComparison': packet['positionRateComparison']}, indent=2))
