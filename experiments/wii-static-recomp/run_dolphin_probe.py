"""Run isolated Windows probes or an unmodified macOS retail reference."""
from pathlib import Path
import argparse
import subprocess
import hashlib
import json
import platform
import re
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--mode', choices=['boot', 'fpr-init'], default='boot')
parser.add_argument('--stage', choices=['baseline', 'icache', 'coherence'], default='baseline')
parser.add_argument('--accurate-cache', choices=['False', 'True'], default='False')
parser.add_argument('--retail-reference', action='store_true')
parser.add_argument('--fifo-reference', type=Path, help='Private verified DFF diagnostic, not a retail game run.')
parser.add_argument('--output', type=Path, help='New isolated directory for a bounded DFF replay.')
parser.add_argument('--seconds', type=int, default=60)
parser.add_argument('--tag', default='')
parser.add_argument('--capture', action='store_true')
args = parser.parse_args()
if args.fifo_reference:
    from pack_stock_gx_replay import read_capture, verify
    assert platform.system() == 'Darwin' and not args.retail_reference
    assert args.output and 1 <= args.seconds <= 30
    replay = args.fifo_reference.resolve()
    metadata = json.loads(replay.with_suffix('.json').read_text())
    assert metadata['result'] == 'DFF_CONTAINER_ROUNDTRIP_NOT_DOLPHIN_OR_GAME_VERIFIED'
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest(replay) == metadata['sha256']
    capture = Path(metadata['capture'])
    assert digest(capture) == metadata['captureSha256']
    state, frames = read_capture(capture)
    verify(replay.read_bytes(), state, frames)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    user = output / 'user'
    user.mkdir()
    exe = Path('work/research/dolphin/macos-2609a/Dolphin.app/Contents/MacOS/Dolphin').resolve()
    command = [str(exe), '-b', '-u', str(user), '-v', 'Metal', '-e', str(replay)]
    for option in ['Dolphin.Interface.ConfirmStop=False', 'Dolphin.Interface.UsePanicHandlers=False',
        'Dolphin.Analytics.PermissionAsked=True', 'Dolphin.Analytics.Enabled=False',
        'Dolphin.DSP.Backend=Null', 'Logger.Options.WriteToFile=True', 'Logger.Options.Verbosity=3',
        'Logger.Logs.VIDEO=True', 'Logger.Logs.BOOT=True']:
        command.extend(['-C', option])
    if args.capture:
        for option in ['Dolphin.Movie.DumpFrames=True', 'Dolphin.Movie.DumpFramesSilent=True',
            'GFX.Settings.DumpFramesAsImages=True']:
            command.extend(['-C', option])
    reason = 'process_exit'
    with (output / 'launch.log').open('wb') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=output)
        print('Owned FIFO reference Dolphin PID', child.pid, flush=True)
        deadline = time.monotonic() + args.seconds
        while child.poll() is None:
            if time.monotonic() >= deadline:
                reason = 'timer'
                break
            images = list(user.glob('Dump/Frames/*.png'))
            if len(images) >= 12 or sum(p.stat().st_size for p in images) >= 64 * 1024 * 1024:
                reason = 'capture_limit'
                break
            if (output / 'launch.log').stat().st_size > 1024 * 1024:
                reason = 'log_limit'
                break
            time.sleep(0.02)
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
    report = {'result': 'DFF_REPLAY_PROCESS_FINISHED_REQUIRES_VISUAL_REVIEW', 'pid': child.pid,
        'exitCode': child.returncode, 'stopReason': reason, 'command': command,
        'dffSha256': digest(replay), 'executableSha256': digest(exe), 'runnerSha256': digest(Path(__file__)),
        'frames': [str(p) for p in sorted(user.glob('Dump/Frames/*.png'))],
        'limits': ['DFF uses captured recompilation inputs, not an original Wii CPU run.',
            'Process termination does not establish renderer fidelity or game acceptance.']}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)
    sys.exit(0)
if args.retail_reference:
    assert platform.system() == 'Darwin'
    assert args.mode == 'boot' and args.stage == 'baseline'
    assert 1 <= args.seconds <= 180
    assert re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
    root = Path('.').resolve()
    exe = root / 'work/research/dolphin/macos-2609a/Dolphin.app/Contents/MacOS/Dolphin'
    dol = root / 'work/private-game/disc/DATA/sys/main.dol'
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    original = sha(dol)
    assert original == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
    output = root / 'work/private-game/static-recomp' / ('dolphin-retail-macos-' + args.tag)
    output.mkdir(exist_ok=False)
    user = output / 'user'
    user.mkdir()
    command = [str(exe), '-b', '-u', str(user), '-v', 'Metal',
        '-C', 'Dolphin.Interface.ConfirmStop=False',
        '-C', 'Dolphin.Analytics.PermissionAsked=True',
        '-C', 'Dolphin.Analytics.Enabled=False',
        '-C', 'Logger.Options.WriteToFile=True',
        '-C', 'Logger.Options.Verbosity=4',
        '-C', 'Logger.Logs.BOOT=True', '-C', 'Logger.Logs.DVDINTERFACE=True',
        '-e', str(dol)]
    if args.capture:
        command.extend(['-C', 'Dolphin.Movie.DumpFrames=True',
            '-C', 'Dolphin.Movie.DumpFramesSilent=True',
            '-C', 'GFX.Settings.DumpFramesAsImages=True'])
    deadline = False
    with (output / 'launch.log').open('wb') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=output)
        print('Owned reference Dolphin PID', child.pid, flush=True)
        try:
            child.wait(timeout=args.seconds)
        except subprocess.TimeoutExpired:
            deadline = True
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
    assert sha(dol) == original
    report = {'pid': child.pid, 'command': command, 'terminalReturncode': child.returncode,
        'deadlineReached': deadline, 'originalDolSha256': original, 'executableSha256': sha(exe),
        'runnerSha256': sha(Path(__file__)), 'logSha256': sha(output / 'launch.log'),
        'frameCount': len(list(user.glob('Dump/Frames/*.png'))),
        'scope': 'Unmodified local Wii DOL in Dolphin; no input injected; visual/behavior acceptance requires inspection.'}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)
    sys.exit(0)
result = subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                         '-File', 'experiments/wii-static-recomp/run_dolphin_probe.ps1', '-Mode', args.mode, '-Stage', args.stage,
                         '-AccurateCache', args.accurate_cache],
                        capture_output=True, text=True, timeout=180)
output = Path('work/private-game/static-recomp/dolphin-icache-probe' if args.stage == 'icache' else 'work/private-game/static-recomp/dolphin-probe')
if args.stage == 'coherence':
    output = Path('work/private-game/static-recomp/dolphin-coherence-probe')
(output / (args.mode + '-launch.log')).write_text(result.stdout + result.stderr)
print(result.stdout, result.stderr, flush=True)
assert result.returncode == 0
