"""Run repeatable, private hidden GL game scenes with timed Wii-button events."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
import threading
from run_stock_pc_play import BoundedCapture, active_game_commands

from build_stock_hidden_input import sha, validate
from verify_wii_us_copy import audit_copy


BUTTONS = {'A': 0x0800, 'B': 0x0400, '1': 0x0200, '2': 0x0001,
    'PLUS': 0x0010, 'UP': 0x0008, 'DOWN': 0x0004,
    'LEFT': 0x0001, 'RIGHT': 0x0002}


def parse_event(raw):
    parts = raw.split(':')
    if len(parts) != 3:
        raise ValueError('Use start_ms:duration_ms:BUTTON[+BUTTON].')
    start, duration = (int(parts[i]) for i in (0, 1))
    if not 0 <= start <= 600000 or not 1 <= duration <= 5000:
        raise ValueError('Event timing is outside the bounded diagnostic range.')
    names = parts[2].upper().split('+')
    if not names or len(set(names)) != len(names) or any(name not in BUTTONS for name in names):
        raise ValueError('Unknown or repeated Wii button.')
    mask = 0
    for name in names:
        mask |= BUTTONS[name]
    return {'startMs': start, 'durationMs': duration, 'buttons': names,
        'mask': mask, 'encoded': f'{start}:{duration}:{mask:x}'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--game-data', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--seconds', required=True, type=int)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--event', action='append', default=[],
        help='start_ms:duration_ms:A+B, or A/B/1/2/PLUS/UP/DOWN/LEFT/RIGHT')
    parser.add_argument('--scenario', type=Path,
        help='Private JSON with an events array in the same format as --event')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600:
        parser.error('--seconds must be in 1..600')
    if args.scenario and args.event:
        parser.error('Use --scenario or repeated --event, not both.')
    if args.scenario:
        scenario = json.loads(args.scenario.read_text())
        if not isinstance(scenario, dict) or not isinstance(scenario.get('events'), list):
            parser.error('Scenario must contain an events array.')
        raw_events = scenario['events']
        if any(not isinstance(event, str) for event in raw_events):
            parser.error('Each scenario event must be a string.')
    else:
        raw_events = args.event
    if len(raw_events) > 256:
        parser.error('At most 256 events')
    try:
        events = [parse_event(raw) for raw in raw_events]
    except ValueError as error:
        parser.error(str(error))
    if any(event['startMs'] + event['durationMs'] > args.seconds * 1000 for event in events):
        parser.error('An event extends beyond the run deadline.')

    build_path = args.build.resolve()
    kind = json.loads(build_path.read_text())['result']
    if kind == 'PRIVATE_VNAND_PERSISTENCE_BUILT_NOT_GAME_VERIFIED':
        from build_stock_vnand_persistence import validate as validate_persistence
        executable = validate_persistence(build_path)
    elif kind == 'RECOVERED_PREVIEW_LINKED_NOT_GAME_VERIFIED':
        from link_recovered_stock_preview import validate as validate_recovered
        executable = validate_recovered(build_path)
    else:
        executable = validate(build_path)
    game_audit = audit_copy(args.game_data)
    game = Path(game_audit['source'])
    config = args.config.resolve()
    run_dir = args.run_dir.resolve()
    if not config.is_file() or not run_dir.is_dir():
        parser.error('Existing config and run directory are required.')
    processes = subprocess.check_output(['/bin/ps', '-axo', 'pid=,command='], text=True)
    if active_game_commands(processes, game):
        parser.error('Another hidden-input game instance uses this DATA.')

    if args.output:
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
    else:
        scratch = Path(__file__).resolve().parents[2] / '_scratch/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix='openshsm-hidden-run-', dir=scratch))
    capture = output / 'captures'
    capture.mkdir(mode=0o700)
    env = {key: value for key, value in os.environ.items()
        if not key.startswith(('NWII_', 'SHSM_', 'OPENSHSM_'))}
    env.update(OPENSHSM_HIDDEN_GL='1', OPENSHSM_AXWII_MIXER='1',
        OPENSHSM_HIDDEN_INPUT_SCHEDULE=';'.join(event['encoded'] for event in events),
        NWII_HEADLESS='0', NWII_WALLTB='1', NWII_SKIP_BOOT_NOTICES='1',
        NWII_SCREENSHOT=str(capture / 'frame'), SDL_AUDIODRIVER='dummy')
    log_path = output / 'runtime.log'
    tail_path = output / 'runtime-tail.log'
    capture_limit = False
    with log_path.open('wb') as log, tail_path.open('wb') as tail:
        bounded = BoundedCapture(log, tail)
        process = subprocess.Popen([str(executable), str(game), str(config)],
            cwd=run_dir, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        def drain():
            while chunk := process.stdout.read(65536):
                bounded.feed(chunk)
            bounded.finish()
        reader = threading.Thread(target=drain)
        reader.start()
        deadline = time.monotonic() + args.seconds
        try:
            while process.poll() is None and time.monotonic() < deadline:
                if len(list(capture.glob('frame_*.bmp'))) >= 64:
                    capture_limit = True
                    break
                time.sleep(0.25)
        finally:
            terminate = process.poll() is None
            timer_expired = terminate and not capture_limit
            if terminate:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            reader.join(timeout=10)
            assert not reader.is_alive(), 'Log reader did not finish after child exit.'
    files = sorted(capture.glob('frame_*.bmp'),
        key=lambda path: int(path.stem.split('_')[1]))
    report = {'result': 'PRIVATE_HIDDEN_INPUT_RUN_NOT_GAME_ACCEPTANCE',
        'pid': process.pid, 'exitCode': process.returncode,
        'timerExpired': timer_expired, 'limitSeconds': args.seconds,
        'captureLimitReached': capture_limit, 'captureLimit': 64,
        'logBytesTotal': bounded.total, 'logPrefixLimit': bounded.prefix_limit,
        'logTailLimit': bounded.tail_limit, 'logTailPath': str(tail_path),
        'hiddenGl': True, 'audioDeviceSkipped': True,
        'buildPath': str(build_path), 'buildSha256': sha(build_path),
        'executableSha256': sha(executable), 'gameDataAudit': game_audit,
        'scenarioPath': str(args.scenario.resolve()) if args.scenario else None,
        'scenarioSha256': sha(args.scenario) if args.scenario else None,
        'configPath': str(config), 'configSha256': sha(config),
        'runDirectory': str(run_dir), 'events': events,
        'logPath': str(log_path), 'logSha256': sha(log_path),
        'capturePaths': [str(path) for path in files],
        'limits': ['Scripted Wii buttons are PC diagnostic inputs in the existing runtime.',
            'Hidden window object exists; SDL_ShowWindow and audio-device opening are skipped.',
            'Capture sampling is every 120 presents and does not prove unsampled frames.',
            'Timer termination is not a natural game exit or gameplay acceptance.']}
    report_path = output / 'result.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], report_path, flush=True)


if __name__ == '__main__':
    main()
