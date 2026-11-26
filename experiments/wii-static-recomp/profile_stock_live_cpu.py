"""Sample only the owned current game PID after actual original decoder progress; no game-code change."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import time

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'live-cpu-attribution'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = root / 'window-decoder-o3/build.json'
build = json.loads(build_path.read_text())
exe = root / 'window-decoder-o3/OpenSHSMStockDecoderO3'
assert sha(exe) == build['executableSha256']
tag = 'cpu-attribution'
movie = root / f'headless-sc-pc-{tag}-movie-timing.jsonl'
assert not movie.exists(), 'Refuse to overwrite prior attribution evidence'
command = [sys.executable, 'experiments/wii-static-recomp/run_stock_baseline.py', '--variant', 'headless-sc-pc',
    '--experimental-executable', str(exe), '--windowed', '--debug-overlay', '--dsp-supply', '--wall-tb',
    '--skip-wii-notices', '--movie-timing', '--seconds', '120', '--tag', tag]
runner = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
lines, pid = [], None
while True:
    line = runner.stdout.readline()
    if not line:
        raise RuntimeError('Runner ended before publishing owned PID')
    lines.append(line)
    match = re.fullmatch(r'Owned stock runtime PID (\d+)\n', line)
    if match:
        pid = int(match[1])
        print(line.strip(), flush=True)
        break
profiled = False
sample_result = None
trigger_rows = 0
started = time.monotonic()
while runner.poll() is None:
    rows = []
    if movie.exists():
        for line in movie.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    decoder_returns = sum(row['site'] == 0x8020A044 for row in rows)
    if decoder_returns >= 20 and not profiled:
        os.kill(pid, 0)
        actual = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'comm='], capture_output=True, text=True, check=True)
        assert Path(actual.stdout.strip()).name == exe.name
        trigger_rows = len(rows)
        sample_path = output / 'owned-cpu-sample.txt'
        sample_command = ['/usr/bin/sample', str(pid), '3', '1', '-file', str(sample_path)]
        print('Sampling owned active decoder PID', pid, 'returns', decoder_returns, flush=True)
        try:
            result = subprocess.run(sample_command, capture_output=True, text=True, timeout=20)
            returncode = result.returncode
            sample_text = result.stdout + result.stderr
        except subprocess.TimeoutExpired as error:
            returncode = None
            def decoded(value):
                return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
            sample_text = decoded(error.stdout) + decoded(error.stderr) + '\nSAMPLER_TIMEOUT_NO_SUCCESS_CLAIM\n'
        (output / 'sample-tool.log').write_text(sample_text)
        sample_result = {'returncode': returncode, 'command': sample_command,
            'sampleSha256': sha(sample_path) if sample_path.exists() else None,
            'toolLogSha256': sha(output / 'sample-tool.log'), 'triggerDecoderReturns': decoder_returns,
            'triggerRecords': trigger_rows}
        profiled = True
        print('Owned sample completed', returncode, flush=True)
    if time.monotonic() - started > 180:
        raise RuntimeError('Observation window exceeded; do not automatically restart owned process')
    time.sleep(0.5)
lines.extend(runner.stdout.readlines())
(output / 'runner.log').write_text(''.join(lines))
run_path = root / f'headless-sc-pc-headless-windowed-{tag}-result.json'
assert run_path.exists(), 'No authoritative terminal result; inspect same runner/PID'
run = json.loads(run_path.read_text())
assert run['pid'] == pid and run['executableSha256'] == build['executableSha256']
(output / 'verification.json').write_text(json.dumps({'result': 'OWNED_LIVE_CPU_SAMPLE_RECORDED' if profiled and
    sample_result['returncode'] == 0 else 'NO_VALID_CPU_SAMPLE_NO_ATTRIBUTION_CLAIM', 'pid': pid,
    'buildSha256': sha(build_path), 'runSha256': sha(run_path), 'runnerReturncode': runner.returncode,
    'sample': sample_result, 'movieSha256': sha(movie) if movie.exists() else None,
    'scriptSha256': sha(Path(__file__)),
    'limits': ['Same existing verified binary, no source/mixer/renderer/guest/clock change.',
        'Sampling after20actual original decoder returns; OS sampling overhead perturbs timings.',
        'Sampled stacks show occupancy, not exact instruction counts or proof of whole-game/Wii behavior.',
        'No OS input/focus/capture; existing deadline runner owns process shutdown.']}, indent=2) + '\n')
print('OWNED_CPU_PROFILE_TERMINAL', run['terminalReturncode'], 'sampled', profiled, flush=True)
