"""Read-only bounded macOS stack sampling of the exact verified experiment PID."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
parser.add_argument('--pid', type=int, required=True)
parser.add_argument('--executable', type=Path)
args = parser.parse_args()
artifacts = args.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp') and re.fullmatch(r'openshsm-run-[A-Za-z0-9_-]+', artifacts.name)
assert args.pid > 0
root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
use_symbols = args.executable is not None and args.executable.name == 'OpenSHSMStockSampleSymbols'
build_path = root / ('window-sample-symbols' if use_symbols else 'window-post-present') / 'build.json'
build = json.loads(build_path.read_text())
component_path = build_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['result'] == ('SAMPLE_SYMBOLS_SECTIONS_SIGNATURE_VERIFIED_FOR_PROFILING_ONLY'
    if use_symbols else 'POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED')
exe = Path(build['executablePath']).resolve()
assert sha(exe) == build['executableSha256']
assert args.executable is None or args.executable.resolve() == exe
print('CPU sample stage: verified executable', flush=True)
ps_command = ['/bin/ps', '-p', str(args.pid), '-o', 'uid=', '-o', 'command=']
identity = subprocess.check_output(ps_command, text=True).strip()
uid, command_line = identity.split(None, 1)
expected_argv = [str(exe), str(root.parents[3] / 'work/private-game/disc/DATA'), str(root / 'user/config.toml')]
assert int(uid) == os.getuid() and shlex.split(command_line) == expected_argv
print('CPU sample stage: verified owned live argv', flush=True)
log = artifacts / 'headless-sc-pc-headless-windowed-post-present-profile.log'
assert log.is_file()
profile = artifacts / 'cpu-sample.txt'
report_path = artifacts / 'cpu-sample-execution.json'
assert not profile.exists() and not report_path.exists()
command = ['/usr/bin/sample', str(args.pid), '5', '1', '-mayDie', '-fullPaths', '-file', str(profile)]
start = time.monotonic_ns()
tool_log = artifacts / 'cpu-sample-tool.log'
timed_out = False
with tool_log.open('w') as stream:
    tool_process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
    print('Owned sample tool PID', tool_process.pid, flush=True)
    try:
        returncode = tool_process.wait(timeout=25)
    except subprocess.TimeoutExpired:
        timed_out = True
        tool_process.terminate()
        try:
            returncode = tool_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            tool_process.kill()
            returncode = tool_process.wait(timeout=3)
end = time.monotonic_ns()
text = profile.read_text() if profile.is_file() else ''
valid = returncode == 0 and f'[{args.pid}]' in text and 'cpu_thread_func' in text and 'Call graph:' in text
report = {'result': 'OWNED_RUNTIME_READ_ONLY_CPU_STACK_SAMPLE_COLLECTED' if valid else 'OWNED_CPU_SAMPLE_FAILED_WITH_TERMINAL_TOOL', 'pid': args.pid,
    'toolPid': tool_process.pid, 'toolReturncode': returncode, 'toolTimedOut': timed_out,
    'command': command, 'identity': identity, 'startHostUs': start // 1000, 'endHostUs': end // 1000,
    'profilePath': str(profile), 'profileSha256': sha(profile) if profile.is_file() else None,
    'toolLogPath': str(tool_log), 'toolLogSha256': sha(tool_log),
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'executableSha256': sha(exe),
    'collectorSha256': sha(Path(__file__)),
    'limits': ['Read-only OS stack sampling perturbs timing;5seconds/1ms nominal interval, not controlled game FPS.',
        'Same user/exact executable argv/verified build checked before sampling; terminal run ownership audit remains required.',
        'No input/focus/priority/QoS/source mutation; CPU stack samples are statistical, not exact decoder-exclusive cost.']}
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], report_path)
if not valid:
    raise SystemExit(1)
