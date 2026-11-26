"""Check launcher policy without spawning or interfering with the user's game."""
from pathlib import Path
import argparse
import ast
import contextlib
import hashlib
import io
import json
import tempfile
from types import SimpleNamespace

source_path = Path(__file__).resolve().parent / 'run_stock_baseline.py'
source = source_path.read_text()
ast.parse(source)
prefix = source[:source.index("project = Path('.')")]
valid = ['--until-closed', '--windowed', '--temporary-evidence', '--variant', 'headless-sc-pc',
    '--experimental-executable', '/private/tmp/fixture/OpenSHSMStockBPParseOrder']
def parse(arguments):
    scope = {'__file__': str(source_path), '__name__': '__test__'}
    with contextlib.redirect_stderr(io.StringIO()):
        exec(compile(prefix, str(source_path), 'exec'), scope)
    return scope['args']

import sys
original_argv = sys.argv
cases = 0
try:
    sys.argv = [str(source_path), *valid]
    args = parse(valid)
    assert args.until_closed and args.seconds == 15
    cases += 1
    rejects = [ ['--seconds', '30'], ['--capture'], ['--movie-timing'], ['--texture-observe'],
        ['--cpu-sample-after-seconds', '0'], ['--test-ab-at-ms', '0'], ['--watch-address', '80004000'],
        ['--trace-only', '80209D80'], ['--dsp-supply', '--thp-dump']]
    for extra in rejects:
        sys.argv = [str(source_path), *valid, *extra]
        try:
            parse(valid + extra)
        except (AssertionError, SystemExit):
            cases += 1
        else:
            raise AssertionError(extra)
    for seconds in (1, 180):
        sys.argv = [str(source_path), '--seconds', str(seconds)]
        assert not parse([]).until_closed
        cases += 1
finally:
    sys.argv = original_argv

cache = Path(tempfile.mkdtemp(prefix='openshsm-user-play-tests-', dir='/private/tmp'))
config = cache / 'config.toml'
config.write_text('user settings retained\n')
start = source.index('if not args.until_closed or not config.exists():')
end = source.index('\nenv = ', start)
block = source[start:end]
exec(compile(block, str(source_path), 'exec'), {'args': SimpleNamespace(until_closed=True), 'config': config})
assert config.read_text() == 'user settings retained\n'
cases += 1
config.unlink()
exec(compile(block, str(source_path), 'exec'), {'args': SimpleNamespace(until_closed=True), 'config': config})
assert 'R5WEA4' in config.read_text()
cases += 1

start = source.index('if args.until_closed:\n    env.pop')
end = source.index('\ntimed_out = False', start)
block = source[start:end]
null = object()
launch_calls = []
sleep_calls = []
class FakeProcess:
    pid = 12345
    def __init__(self, code):
        self.code = code
    def poll(self):
        return self.code
    def terminate(self):
        raise AssertionError('Unexpected terminate')
    def kill(self):
        raise AssertionError('Unexpected kill')
    def wait(self, **kwargs):
        raise AssertionError('Unexpected wait/deadline')

for code in (None, 7):
    def spawn(argv, **kwargs):
        assert kwargs['start_new_session'] is True
        assert kwargs['stdin'] is null and kwargs['stdout'] is null and kwargs['stderr'] is null
        assert 'NWII_SAMPLE' not in kwargs['env']
        launch_calls.append((argv, kwargs))
        return FakeProcess(code)
    def stop(value):
        raise SystemExit(value)
    scope = {'args': SimpleNamespace(until_closed=True, debug_overlay=True, wall_tb=True, skip_wii_notices=True),
        'env': {'NWII_SAMPLE': '1'}, 'subprocess': SimpleNamespace(Popen=spawn, DEVNULL=null),
        'exe': Path('/private/tmp/fixture/OpenSHSMStockBPParseOrder'), 'game': cache, 'config': config,
        'work': cache, 'artifact_root': cache, 'label': f'fixture-{code}', 'sha': lambda path: 'fixture-hash',
        'original_hash': 'fixture-DOL', '__file__': str(source_path), 'json': json, 'Path': Path,
        'time': SimpleNamespace(sleep=sleep_calls.append), 'sys': SimpleNamespace(exit=stop)}
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            exec(compile(block, str(source_path), 'exec'), scope)
        except SystemExit as error:
            assert code is None and error.code == 0
        except AssertionError:
            assert code == 7
        else:
            raise AssertionError('Detached branch must exit or reject early death')
    record = json.loads((cache / f'fixture-{code}-result.json').read_text())
    assert record['seconds'] is None and not record['deadlineReached']
    assert record['terminalReturncode'] == code
    cases += 1
assert len(launch_calls) == 2 and sleep_calls == [1, 1]
report = {'result': 'USER_PLAY_POLICY_ARGUMENTS_CONFIG_DETACH_NO_TIMER_PASS', 'cases': cases,
    'launcherSha256': hashlib.sha256(source.encode()).hexdigest(),
    'verifierSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'limits': ['Mock subprocess launch/poll only; actual existing user game was neither restarted nor controlled.',
        'Checks policy/config preservation, not actual detached launch, UI, gameplay or Wii runtime fidelity.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], cases, path)
