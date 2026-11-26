"""Launch a verified local macOS build with the owner's extracted Wii DATA."""
from pathlib import Path
import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys

from export_stock_wii_us_copy import digest
from run_stock_pc_play import BoundedCapture, active_game_commands
from verify_wii_us_copy import audit_copy
from launcher_locale import runtime_environment, text


def source_version():
    version = re.search(r'^#define OPENSHSM_RECOMP_BUILD_VERSION "([0-9.]+)"$',
        Path(__file__).with_name('BuildVersion.h').read_text(), re.M)
    if not version:
        raise ValueError('BuildVersion.h differs')
    return version.group(1)


def validate(build_dir, game_data, user_dir):
    build_dir = Path(build_dir).expanduser().resolve(strict=True)
    game = Path(audit_copy(game_data)['source']).resolve(strict=True)
    user_dir = Path(user_dir).expanduser().absolute()
    if not user_dir.parent.is_dir():
        raise ValueError('User directory parent does not exist')
    user_dir = user_dir.parent.resolve(strict=True) / user_dir.name
    if user_dir == game or game in user_dir.parents or \
            user_dir == build_dir or build_dir in user_dir.parents:
        raise ValueError('User directory must be outside Wii DATA and build output')
    report = json.loads((build_dir / 'build-result.json').read_text())
    if report['result'] != 'OWNER_WII_MACOS_SOURCE_COMPILED_LINKED_NOT_GAME_VERIFIED' or \
            report['dolSha256'] != digest(game / 'sys/main.dol'):
        raise ValueError('Build and Wii copy differ')
    version = source_version()
    if report['version'] != version:
        raise ValueError('Build version differs from public source')
    name = Path(report['executable']).name
    if name != f'OpenSHSM-{version}':
        raise ValueError('Executable name differs from build version')
    executable = build_dir / name
    if executable.is_symlink() or not executable.is_file() or \
            digest(executable) != report['executableSha256']:
        raise ValueError('Built executable is missing or has changed')
    if user_dir.is_symlink():
        raise ValueError('User directory must not be a symlink')
    return executable, game, user_dir


def launch(build_dir, game_data, user_dir, check_only=False, *, show_launcher=True,
        settings_only=False, image=None, dolphin_tool=None):
    from launcher_import import resolve_game_data
    if (check_only or game_data is not None) and image is not None:
        raise ValueError('--import-image cannot be combined with --check-only or --game-data')
    if game_data is None:
        game_data = resolve_game_data(None, user_dir,
            interactive=show_launcher and not check_only, image=image, dolphin_tool=dolphin_tool)
    if game_data is None:
        return {'result': 'OWNER_LAUNCH_CANCELLED_NOT_GAME_RUN'}
    if not Path(build_dir).expanduser().is_dir():
        raise ValueError(text('Wii DATA is ready: ', 'Wii DATA готова: ') + str(game_data) +
            text('. Build not found: ', '. Нет сборки: ') + str(build_dir) +
            text('. Run prepare_build_stock_owner_macos.py as described in README.md or specify --owner-build.',
                '. Выполните prepare_build_stock_owner_macos.py по README.md или укажите --owner-build.'))
    executable, game, user_dir = validate(build_dir, game_data, user_dir)
    if check_only:
        return {'result': 'OWNER_WII_LAUNCH_INPUTS_VALIDATED_NOT_GAME_RUN',
            'executable': str(executable), 'gameData': str(game)}
    processes = subprocess.check_output(['/bin/ps', '-axo', 'pid=,command='], text=True)
    if active_game_commands(processes, game):
        raise RuntimeError('Another OpenSHSM process is using this Wii DATA')
    user_dir.mkdir(mode=0o700, exist_ok=True)
    config = user_dir / 'config.toml'
    if config.is_symlink():
        raise ValueError('Config must not be a symlink')
    if not config.exists():
        shutil.copyfile(Path(__file__).with_name('config.example.toml'), config)
    if not config.is_file():
        raise ValueError('Config is not a file')
    lock = (user_dir / 'launch.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise RuntimeError('This user directory already has a running game') from error
    if show_launcher:
        from launcher_settings import show_settings
        accepted = show_settings(config, settings_only)
        if not accepted or settings_only:
            return {'result': 'OWNER_SETTINGS_SAVED_NOT_GAME_RUN' if accepted else 'OWNER_LAUNCH_CANCELLED_NOT_GAME_RUN'}
    environment = {key: value for key, value in os.environ.items()
        if not key.startswith(('NWII_', 'SHSM_', 'OPENSHSM_'))
        and key not in ('SDL_AUDIODRIVER', 'SDL_VIDEODRIVER')}
    environment.update(NWII_HEADLESS='0', NWII_WALLTB='1',
        NWII_SKIP_BOOT_NOTICES='1', OPENSHSM_AXWII_MIXER='1')
    if os.environ.get('OPENSHSM_TRACE_DESKTOP_LOOK') == '1':
        environment['OPENSHSM_TRACE_DESKTOP_LOOK'] = '1'
    from launcher_settings import controller_icon_environment
    environment.update(controller_icon_environment(user_dir))
    environment.update(runtime_environment())
    with (user_dir / 'runtime.log').open('wb') as prefix, \
            (user_dir / 'runtime-tail.log').open('wb') as tail:
        capture = BoundedCapture(prefix, tail)
        process = subprocess.Popen([str(executable), str(game), str(config)],
            cwd=user_dir, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            while chunk := process.stdout.read(65536):
                capture.feed(chunk)
            code = process.wait()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            capture.finish()
    result = {'result': 'OWNER_WII_MACOS_GAME_PROCESS_EXITED_NOT_FULL_GAME_ACCEPTANCE',
        'exitCode': code, 'executable': executable.name,
        'totalLogBytes': capture.total}
    (user_dir / 'last-run.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--game-data', type=Path)
    parser.add_argument('--import-image', type=Path)
    parser.add_argument('--dolphin-tool', type=Path)
    from launcher_import import default_user_dir
    parser.add_argument('--user-dir', type=Path, default=default_user_dir())
    parser.add_argument('--check-only', action='store_true')
    settings = parser.add_mutually_exclusive_group()
    settings.add_argument('--no-settings', action='store_true')
    settings.add_argument('--settings-only', action='store_true')
    args = parser.parse_args()
    if args.dolphin_tool and not args.import_image:
        parser.error('--dolphin-tool requires --import-image')
    if args.settings_only and args.check_only:
        parser.error('--settings-only cannot be combined with --check-only')
    result = launch(args.build_dir, args.game_data, args.user_dir, args.check_only,
        show_launcher=not args.no_settings, settings_only=args.settings_only,
        image=args.import_image, dolphin_tool=args.dolphin_tool)
    print(json.dumps(result, indent=2), flush=True)
    if result.get('exitCode', 0):
        raise SystemExit(result['exitCode'])


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f'OpenSHSM: {error}', file=sys.stderr)
        raise SystemExit(1) from error
