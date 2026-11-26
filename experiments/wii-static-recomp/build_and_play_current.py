"""Local macOS entry point for the retained, current Wii recompilation sources."""
from pathlib import Path
import argparse
import fcntl
import json
import os
import subprocess
import sys

from link_recovered_stock_preview import validate
from run_stock_pc_play import BoundedCapture, active_game_commands
from verify_wii_us_copy import audit_copy
from launcher_locale import runtime_environment, text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--game-data', type=Path,
        help='Verified Wii US R5WEA4 rev0 DATA directory or its parent')
    parser.add_argument('--import-image', type=Path)
    parser.add_argument('--dolphin-tool', type=Path)
    parser.add_argument('--import-only', action='store_true', help='Prepare Wii data without building or launching')
    parser.add_argument('--config', type=Path,
        help='Existing config.toml outside the game DATA directory')
    parser.add_argument('--owner-build', type=Path,
        help='Launch an existing owner build through the portable owner launcher')
    parser.add_argument('--user-dir', type=Path,
        help='Persistent directory for owner config.toml, saves and bounded logs')
    parser.add_argument('--check-only', action='store_true',
        help='Validate owner build and Wii DATA without launching')
    settings = parser.add_mutually_exclusive_group()
    settings.add_argument('--no-settings', action='store_true', help='Launch without the settings window')
    settings.add_argument('--settings-only', action='store_true', help='Edit settings without starting the game')
    args = parser.parse_args()
    if args.settings_only and (args.check_only or args.build_only):
        parser.error('--settings-only cannot be combined with build/check-only')
    from launcher_import import default_user_dir, resolve_game_data
    if args.dolphin_tool and not args.import_image:
        parser.error('--dolphin-tool requires --import-image')
    if args.import_only:
        if args.build_only or args.check_only or args.settings_only or args.config:
            parser.error('--import-only cannot be combined with build/check/settings-only or --config')
        game = resolve_game_data(args.game_data, args.user_dir or default_user_dir(),
            interactive=not args.no_settings, image=args.import_image, dolphin_tool=args.dolphin_tool)
        print(json.dumps({'result': 'WII_IMPORT_READY_NOT_GAME_RUN' if game else 'WII_IMPORT_CANCELLED',
            'gameData': str(game) if game else None}, indent=2))
        return
    if args.owner_build:
        if args.config or args.build_only:
            parser.error('Owner mode uses --user-dir/config.toml and an existing build')
        from launch_stock_owner_macos import launch
        result = launch(args.owner_build, args.game_data, args.user_dir or default_user_dir(), args.check_only,
            show_launcher=not args.no_settings, settings_only=args.settings_only,
            image=args.import_image, dolphin_tool=args.dolphin_tool)
        print(json.dumps(result, indent=2), flush=True)
        if result.get('exitCode', 0):
            raise RuntimeError(text(f"Game exited with code {result['exitCode']}.",
                f"Игра завершилась с кодом {result['exitCode']}."))
        return
    public = Path(__file__).resolve().parent
    project = public.parents[1]
    preview = project / 'work/private-game/static-recomp/current-preview'
    if not preview.is_dir():
        if args.config:
            parser.error('Public owner mode uses --user-dir/config.toml')
        from launch_stock_owner_macos import launch, source_version
        build = project / 'build' / source_version() / 'build'
        if args.build_only:
            parser.error('Public sources require prepare_build_stock_owner_macos.py; see README.md')
        result = launch(build, args.game_data, args.user_dir or default_user_dir(), args.check_only,
            show_launcher=not args.no_settings, settings_only=args.settings_only,
            image=args.import_image, dolphin_tool=args.dolphin_tool)
        print(json.dumps(result, indent=2), flush=True)
        if result.get('exitCode', 0):
            raise RuntimeError(text(f"Game exited with code {result['exitCode']}.",
                f"Игра завершилась с кодом {result['exitCode']}."))
        return
    if args.user_dir or args.check_only:
        parser.error('--user-dir and --check-only require --owner-build in the development tree')
    if args.import_image:
        parser.error('Use --import-only or --owner-build when importing an image')
    inputs = preview / 'user-build-inputs'
    output = preview / 'user-build'
    output.mkdir(exist_ok=True)
    lock = (output / 'launcher.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError(text('A build or game is already running from this launcher.',
            'Сборка или игра уже запущена этим ярлыком.'))
    owner_root = preview / 'owner-build'
    default_game = (project / 'work/private-game/disc/DATA' if owner_root.is_dir() else
        project / '_scratch/tmp/wii-import-rev0-20261011/DATA')
    game = Path(audit_copy(args.game_data or default_game)['source'])
    default_config = (game.parent / 'config.toml' if args.game_data else
        preview / 'owner-user/config.toml' if owner_root.is_dir() else
        game.parent / 'persist-permission-user/config.toml')
    config = (args.config or default_config).expanduser().absolute()
    if not config.is_file():
        raise RuntimeError(text('Existing game settings were not found: ',
            'Не найдены существующие настройки игры: ') + str(config))
    config = config.resolve(strict=True)
    run_dir = config.parent
    if run_dir == game or game in run_dir.parents:
        raise RuntimeError(text('Settings and working directory must be outside Wii DATA: ',
            'Настройки и рабочий каталог должны находиться вне Wii DATA: ') + str(config))
    if not args.build_only:
        processes = subprocess.check_output(['/bin/ps', '-axo', 'pid=,command='], text=True)
        if active_game_commands(processes, game):
            raise RuntimeError(text('Close the running OpenSHSM process first.',
                'Сначала закройте уже запущенную OpenSHSM.'))
    if owner_root.is_dir():
        from launch_stock_owner_macos import source_version, validate as validate_owner
        executable, game, _ = validate_owner(owner_root / source_version(), game, run_dir)
        print(text('Verified existing owner build: ',
            'Проверена готовая owner-сборка: ') + str(executable), flush=True)
    else:
        command = [sys.executable, str(public / 'link_recovered_stock_preview.py'),
            '--preview', str(preview), '--output', str(output), '--optimize-runtime', '--dc-zero',
            '--lhaux', '--negative-ios-fd', '--desktop-input-sources', str(inputs / 'desktop-input')]
        for flag, name in [('renderer', 'renderer_gl.cpp'), ('shader', 'tev_shader_gen.cpp'),
                ('main', 'main.cpp'), ('gx', 'gx.cpp'), ('fifo', 'fifo_parser.cpp')]:
            command.extend(['--' + flag + '-source', str(inputs / name)])
        print(text('Building the current OpenSHSM on SSD…',
            'Сборка актуальной OpenSHSM на SSD…'), flush=True)
        subprocess.run(command, cwd=project, check=True)
        executable = validate(output / 'build.json')
        print(text('Build and file verification finished.',
            'Сборка и проверка файлов завершены.'), flush=True)
    if args.build_only:
        return
    if not args.no_settings:
        from launcher_settings import show_settings
        accepted = show_settings(config, args.settings_only)
        if not accepted or args.settings_only:
            return
    env = {key: value for key, value in os.environ.items()
        if not key.startswith(('NWII_', 'SHSM_', 'OPENSHSM_'))
        and key not in ('SDL_AUDIODRIVER', 'SDL_VIDEODRIVER')}
    env.update(NWII_HEADLESS='0', NWII_DEBUG_OVERLAY='1', NWII_WALLTB='1',
        NWII_SKIP_BOOT_NOTICES='1', OPENSHSM_AXWII_MIXER='1')
    if os.environ.get('OPENSHSM_TRACE_DESKTOP_LOOK') == '1':
        env['OPENSHSM_TRACE_DESKTOP_LOOK'] = '1'
    from launcher_settings import controller_icon_environment
    env.update(controller_icon_environment(run_dir))
    env.update(runtime_environment())
    print(text('Launching with audio and overlay. F1 shows controls. Close the game to exit.',
        'Запуск со звуком и оверлеем. F1 — управление. Для выхода закройте игру.'), flush=True)
    with (output / 'runtime.log').open('wb') as prefix, (output / 'runtime-tail.log').open('wb') as tail:
        capture = BoundedCapture(prefix, tail)
        process = subprocess.Popen([str(executable), str(game), str(config)], cwd=run_dir,
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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
    (output / 'last-run.json').write_text(json.dumps({'exitCode': code,
        'executable': str(executable), 'totalLogBytes': capture.total,
        'automaticInput': False, 'audio': True, 'debugOverlay': True}, indent=2) + '\n')
    if code:
        raise RuntimeError(text(f'Game exited with code {code}. Logs: {output}',
            f'Игра завершилась с кодом {code}. Журналы: {output}'))


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(f'OpenSHSM: {error}', file=sys.stderr)
        sys.exit(1)
