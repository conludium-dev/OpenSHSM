"""Audit owned live VI reason totals together with SDK cadence and exact movie inputs."""
from pathlib import Path
import hashlib
import json
import re

base = Path('experiments/wii-static-recomp/audit_stock_current_vi_timer.py')
script = base.read_text()
script = script.replace('window-current-vi-timer', 'window-vi-timer-profile')
script = script.replace('current-vi-timer', 'vi-timer-profile')
script = script.replace('"parent_path = root / \'window-dec-ee-gate/build.json\'"',
    '"parent_path = root / \'window-current-vi-timer/build.json\'"')
script = script.replace('CURRENT_TIMER_MAIN_ONLY_LINK_SOURCE_SDK_MARKERS_VERIFIED',
    'VI_TIMER_PROFILE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL')
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
artifacts, output = scope['artifacts'], scope['output']
run = scope['run']
assert run['viTimerProfile']
log = artifacts / 'headless-sc-pc-headless-windowed-vi-timer-profile.log'
assert hashlib.sha256(log.read_bytes()).hexdigest() == run['logSha256']
keys = ['period', 'registrationHz', 'currentHz', 'due', 'lateTicks', 'maxLate',
    'masked', 'callback', 'pending', 'busy', 'raised']
rows = [dict(zip(keys, map(int, values))) for values in re.findall(
    r'^\[VI_TIMER\] ' + ' '.join(key + r'=(\d+)' for key in keys) + r'$', log.read_text(), re.M)]
assert rows
for index, row in enumerate(rows):
    assert sum(row[key] for key in keys[6:]) == row['due']
    assert row['period'] > 0 and row['registrationHz'] > 0 and row['currentHz'] > 0
    if index:
        for key in keys[3:]:
            assert row[key] >= rows[index - 1][key]
        assert row['period'] == rows[0]['period']
        assert row['registrationHz'] == rows[0]['registrationHz']
last = rows[-1]
report = {
    'result': 'LIVE_EXISTING_VI_TIMER_REASONS_SDK_PACKETS_AUDITED',
    'runSha256': scope['sha'](scope['run_path']), 'logSha256': scope['sha'](log),
    'buildSha256': scope['sha'](output / 'build.json'),
    'componentSha256': scope['sha'](output / 'component-verification.json'),
    'auditorSha256': scope['sha'](Path(__file__)), 'baseAuditorSha256': scope['sha'](base),
    'rows': rows, 'last': last,
    'configuredFrequency': last['registrationHz'] / last['period'],
    'currentPeriodFrequency': last['currentHz'] / last['period'],
    'meanLatenessMilliseconds': last['lateTicks'] * 1000 / last['currentHz'] / last['due'],
    'maximumLatenessMilliseconds': last['maxLate'] * 1000 / last['currentHz'],
    'reasonFractions': {key: last[key] / last['due'] for key in keys[6:]},
    'phaseSummary': scope['packet']['currentPhaseSummary'],
    'positionRates': scope['packet']['positionRateComparison'],
    'packetAuditSha256': scope['sha'](output / 'live-input-audit.json'),
    'limits': ['Cumulative last emitted sample may omit fewer than60 final firings; not a complete IRQ trace.',
        'Late scheduler coalescing can omit nominal periods; due counters are actual callback calls only.',
        'Periodic stderr can perturb timing; original ordered gating unchanged, no hardware correctness claim.',
        'Source positions measure decoder inputs, not independent displayed frame timing or full gameplay acceptance.']}
(output / 'vi-reason-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({key: report[key] for key in ['last', 'reasonFractions',
    'configuredFrequency', 'meanLatenessMilliseconds', 'maximumLatenessMilliseconds', 'phaseSummary']}, indent=2))
