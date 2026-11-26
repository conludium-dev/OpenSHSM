"""Reuse actual callback/frame contracts, then SDK and original emitted SC resume tests with only IOS optimized."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-ios-o2'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
assert (output / 'ios.cpp').read_bytes() == Path(build['originalSourcePath']).read_bytes()
assert sha(output / 'ios.cpp') == build['sourceSha256'] == build['originalSourceSha256']
assert sha(output / 'ios.cpp.o') == build['objectSha256']
assert build['arguments'] == build['originalArguments'] + ['-O2']
base = Path('experiments/wii-static-recomp/verify_stock_callback_profile.py')
script = base.read_text()
header_block = '''header = (output / 'stock_movie_timing.h').read_text()
for before, after in reversed(build['headerPatches']):
    assert header.count(after) == 1
    header = header.replace(after, before, 1)
assert header == (root / 'window-movie-input/stock_movie_timing.h').read_text()
'''
profile_block = '''    first, last = events[0]['callbackProfile'], events[1]['callbackProfile']
    assert all(a <= b for a, b in zip(first, last)) and last[0] > first[0] and last[8] == 0
'''
patches = [("output = root / 'window-callback-profile'", "output = root / 'window-ios-o2'"),
    (header_block, ''), ("flags = build['changes']['37']['arguments']", "flags = parent['changes']['37']['arguments']"),
    (profile_block, ''), ("'profile': last,", ''),
    ('CALLBACK_PROFILE_ACTUAL_NONLOCAL4_FRAME_STATE_IDENTICAL3', 'IOS_O2_CALLBACK4_FRAME_STATE_IDENTICAL3')]
for before, after in patches:
    assert script.count(before) >= 1
    script = script.replace(before, after)
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
report['baseVerifierSha256'] = sha(base)
report['limits'] = ['Actual baseline/O2 callback queue gating and two native nonlocal handoff paths selected endpoints identical.',
    'Same HM1PLY15 whole YUV/selected final PPC state/instruction count exact, existing observer enabled.',
    'Identical IOS source/O2 only, all other archive members/masterO0/all75guests/main/audio retained.',
    'Native prepared fixtures, not physical Wii IRQ/whole game/visual/audio/profile/controller acceptance.']
parent = json.loads((root / 'window-movie-input/build.json').read_text())
temporary = Path(tempfile.mkdtemp(prefix='openshsm-ios-o2-regressions-', dir='/private/tmp'))
flags = parent['changes']['37']['arguments']
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
regressions = []
for name, source, marker in [('sdk', Path('experiments/wii-static-recomp/stock_sdk_enable_resume_probe.cpp'), 'RESUME '),
    ('sc', Path('experiments/wii-static-recomp/stock_sc_resume_probe.cpp'), 'SYNCHRONIZED_SC_PC_RETURN_PASS')]:
    obj, exe = temporary / f'{name}.cpp.o', temporary / name
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-2500:]
    command = list(build['linkCommand'])
    main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
    command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    command.insert(1, str(obj))
    if name == 'sc':
        proof_path = root / 'sc-emitter-research/native-execution/comparison.json'
        proof = json.loads(proof_path.read_text())
        corrected = proof_path.parent / 'corrected.cpp.o'
        assert sha(corrected) == proof['records']['corrected']['objectSha256']
        command.insert(1, str(corrected))
    command[command.index('-o') + 1] = str(exe)
    result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr[-2500:]
    run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
    log = output / f'{name}-regression.log'
    log.write_text(run.stdout + run.stderr)
    assert run.returncode == 0 and marker in run.stdout, run.stdout + run.stderr
    if name == 'sdk':
        assert sum(line.startswith('RESUME ') for line in run.stdout.splitlines()) == 7
    regressions.append({'name': name, 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'executablePath': str(exe), 'executableSha256': sha(exe), 'logSha256': sha(log)})
report.update(result='IOS_O2_CALLBACK4_FRAME3_SDK7_SC3_PASS', regressions=regressions,
    verifierSha256=sha(Path(__file__)))
report['limits'].append('SDK7 continuation and emitted SC3 alignment/queued callback/save-load/return regressions passed; full hardware vector path not exercised.')
report_path.write_text(json.dumps(report, indent=2) + '\n')
print('IOS_O2_CALLBACK4_FRAME3_SDK7_SC3_PASS')
