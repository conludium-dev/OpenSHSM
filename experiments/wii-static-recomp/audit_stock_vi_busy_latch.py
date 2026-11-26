"""Compare actual busy-latch candidate SDK, owned movie source progression and audio."""
from pathlib import Path
import hashlib
import json

base = Path('experiments/wii-static-recomp/audit_stock_current_vi_timer.py')
script = base.read_text()
script = script.replace('window-current-vi-timer', 'window-vi-busy-latch')
script = script.replace('current-vi-timer', 'vi-busy-latch')
script = script.replace('"parent_path = root / \'window-dec-ee-gate/build.json\'"',
    '"parent_path = root / \'window-current-vi-timer/build.json\'"')
script = script.replace('CURRENT_TIMER_MAIN_ONLY_LINK_SOURCE_SDK_MARKERS_VERIFIED',
    'VI_BUSY_LATCH_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL')
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
root, output = scope['root'], scope['output']
packet = scope['packet']
prior_path = root / 'window-current-vi-timer/live-input-audit.json'
prior = json.loads(prior_path.read_text())
assert prior['result'] == 'CURRENT_TIMER_ONLY_LATE_PACKET_VISUAL_AUDIO_AUDITED'
report = {
    'result': 'VI_BUSY_LATCH_LIVE_SDK_SOURCE_PROGRESSION_PACKETS_AUDITED',
    'buildSha256': scope['sha'](output / 'build.json'),
    'runSha256': scope['sha'](scope['run_path']),
    'componentSha256': scope['sha'](output / 'component-verification.json'),
    'auditorSha256': scope['sha'](Path(__file__)), 'baseAuditorSha256': scope['sha'](base),
    'phaseSummary': packet['currentPhaseSummary'],
    'positionRates': packet['positionRateComparison'],
    'counterfreeTimerOnlyBaseline': prior['positionRateComparison']['timerOnly'],
    'counterfreeTimerOnlyBaselineSha256': scope['sha'](prior_path),
    'artifactDirectory': str(scope['artifacts']),
    'packetAuditSha256': scope['sha'](output / 'live-input-audit.json'),
    'limits': ['Only existing periodic busy gate removed, existing safe delivery retained; no second queue/catch-up.',
        'Original decoder input positions, not independently observed displayed timing; under-speed or over-speed must block promotion.',
        'Separate live sessions/IRQ/context histories are not controlled exclusive improvement percentages.',
        'Sparse captures/audio counters do not prove full flicker/speaker/profile/save/controller/hardware acceptance.']}
(output / 'busy-latch-live-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({'phaseSummary': report['phaseSummary'], 'positionRates': report['positionRates'],
    'counterfreeTimerOnlyBaseline': report['counterfreeTimerOnlyBaseline']}, indent=2))
