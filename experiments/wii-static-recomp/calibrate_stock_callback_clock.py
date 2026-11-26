"""Measure empty sampled ticket overhead with the current same O2 flags; not an exact live CPU subtraction."""
from pathlib import Path
import hashlib
import json
import os
import re
import statistics
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-callback-o2-profile'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
audit_path = output / 'live-profile-audit.json'
audit = json.loads(audit_path.read_text())
assert audit['result'] == 'CURRENT_IOS_O2_EXACT_LATE_PACKET_CALLBACK_PROFILE_AUDITED'
assert audit['buildSha256'] == sha(build_path)
source = Path('experiments/wii-static-recomp/stock_callback_clock_calibration.cpp').resolve()
temporary = Path(tempfile.mkdtemp(prefix='openshsm-callback-clock-', dir='/private/tmp'))
exe = temporary / 'calibration'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['iosArguments'],
    '-c', str(source), '-o', str(temporary / 'calibration.o')], capture_output=True, text=True, timeout=30)
assert compiled.returncode == 0, compiled.stderr[-2500:]
sdk = build['iosArguments'][build['iosArguments'].index('-isysroot') + 1]
linked = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', sdk,
    str(temporary / 'calibration.o'), '-o', str(exe)], capture_output=True, text=True, timeout=30)
assert linked.returncode == 0, linked.stderr[-2500:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env['NWII_MOVIE_TIMING'] = 'calibration-only-no-game'
rows = []
for iteration in range(5):
    run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, run.stdout + run.stderr
    match = re.fullmatch(r'EMPTY_CALLBACK_CLOCK_CALIBRATION_PASS (\d+) (\d+)\n', run.stdout)
    assert match and int(match[1]) == 2048
    rows.append({'iteration': iteration, 'ordinarySamples': int(match[1]), 'sampleCpuNs': int(match[2]),
        'meanCpuNs': int(match[2]) / int(match[1])})
report = {'result': 'SAME_O2_EMPTY_CALLBACK_CLOCK_OVERHEAD_CALIBRATED5',
    'buildSha256': sha(build_path), 'profileAuditSha256': sha(audit_path), 'sourceSha256': sha(source),
    'helperSha256': sha(Path('experiments/wii-static-recomp/stock_callback_profile.h')),
    'executablePath': str(exe), 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
    'rows': rows, 'emptyMeanMedianNs': statistics.median(row['meanCpuNs'] for row in rows),
    'liveOrdinarySampleMeanCpuNs': audit['summary']['ordinarySampleMeanCpuNs'],
    'limits': ['Same helper and current IOS O2 flags, empty body with volatile flag reads, five separate native synthetic runs.',
        'Includes clock/wrapper/counter measurement cost; compiler shape/cache/host conditions differ from actual IOS body.',
        'Not an exact subtractable constant or exclusive CPU percentage; original sampled mean must not be extrapolated naively.',
        'No game/runtime/IRQ/clock/visual/audio change or speedup; calibration evidence only.']}
(output / 'clock-calibration.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({'emptyMeanMedianNs': report['emptyMeanMedianNs'],
    'liveOrdinarySampleMeanCpuNs': report['liveOrdinarySampleMeanCpuNs'], 'rows': rows}, indent=2))
