"""Calibrate a private clock-only variant of the existing counter helper with current O2 flags."""
from pathlib import Path
import hashlib
import json
import os
import re
import statistics
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'callback-wall-clock'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
ios_path = root / 'window-ios-o2/build.json'
ios = json.loads(ios_path.read_text())
original = public / 'stock_callback_profile.h'
text = original.read_text()
assert text.count('CLOCK_THREAD_CPUTIME_ID') == 1
replacement = text.replace('CLOCK_THREAD_CPUTIME_ID', 'CLOCK_MONOTONIC_RAW', 1)
assert replacement.replace('CLOCK_MONOTONIC_RAW', 'CLOCK_THREAD_CPUTIME_ID', 1) == text
cache = Path(tempfile.mkdtemp(prefix='openshsm-wall-clock-', dir='/private/tmp'))
helper = cache / original.name
helper.write_text(replacement)
flags = ios['arguments']
sdk = flags[flags.index('-isysroot') + 1]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
records, rows = [], []
for name, original_probe in [('component', public / 'stock_callback_profile_probe.cpp'),
    ('calibration', public / 'stock_callback_clock_calibration.cpp')]:
    source, obj, exe = cache / original_probe.name, cache / f'{name}.o', cache / name
    source.write_bytes(original_probe.read_bytes())
    compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=30)
    assert compiled.returncode == 0, compiled.stderr[-2500:]
    linked = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', sdk,
        str(obj), '-o', str(exe)], capture_output=True, text=True, timeout=30)
    assert linked.returncode == 0, linked.stderr[-2500:]
    if name == 'component':
        for active in (False, True):
            selected = dict(env)
            if active:
                selected['NWII_MOVIE_TIMING'] = 'wall-component'
            run = subprocess.run([str(exe)], env=selected, capture_output=True, text=True, timeout=10)
            marker = 'CALLBACK_PROFILE_RETURN_EE_CALLBACK_NONLOCAL_COUNTS_PASS' if active else 'CALLBACK_PROFILE_DISABLED_PASS'
            assert run.returncode == 0 and marker in run.stdout, run.stdout + run.stderr
    else:
        selected = dict(env, NWII_MOVIE_TIMING='wall-calibration')
        for iteration in range(5):
            run = subprocess.run([str(exe)], env=selected, capture_output=True, text=True, timeout=15)
            match = re.fullmatch(r'EMPTY_CALLBACK_CLOCK_CALIBRATION_PASS (\d+) (\d+)\n', run.stdout)
            assert run.returncode == 0 and match and int(match[1]) == 2048, run.stdout + run.stderr
            rows.append({'iteration': iteration, 'samples': int(match[1]), 'sampleWallNs': int(match[2]),
                'emptyMeanWallNs': int(match[2]) / int(match[1])})
    records.append({'name': name, 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'executablePath': str(exe), 'executableSha256': sha(exe)})
(output / 'verification.json').write_text(json.dumps({
    'result': 'WALL_CLOCK_ONLY_HELPER_NONLOCAL_COMPONENT_CALIBRATION5_PASS',
    'iosBuildSha256': sha(ios_path), 'originalHelperPath': str(original), 'originalHelperSha256': sha(original),
    'helperPath': str(helper), 'helperSha256': sha(helper), 'clock': 'CLOCK_MONOTONIC_RAW',
    'counterOrder': ['calls', 'ordinaryReturns', 'trueReturns', 'ee0Entries', 'inCallbackEntries',
        'sampledEntries', 'sampledOrdinaryReturns', 'sampleWallNs', 'sampleClockFailures', 'successfulContextRestores'],
    'emptyMeanMedianWallNs': statistics.median(row['emptyMeanWallNs'] for row in rows), 'rows': rows,
    'records': records, 'scriptSha256': sha(Path(__file__)),
    'limits': ['Same existing helper with ONLY diagnostic clock identifier replaced, same current O2 flags.',
        'WALL includes preemption; not CPU time, exclusive body cost or exact subtractable calibration constant.',
        'Disabled/ordinary/sampled native longjmp counters pass, five empty synthetic calibration runs; no game behavior change yet.',
        'Private temporary helper variant, original public helper/old evidence untouched.']}, indent=2) + '\n')
print('WALL_CLOCK_ONLY_HELPER_NONLOCAL_COMPONENT_CALIBRATION5_PASS',
    statistics.median(row['emptyMeanWallNs'] for row in rows))
