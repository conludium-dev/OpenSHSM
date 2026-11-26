"""Run the actual compiled input sources against controlled SDL state, headless."""
from pathlib import Path
import argparse
import json
import subprocess
import tempfile

from stock_debug_font_build import sha
from stock_pause_input_validation import validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pause-input-build', type=Path, required=True)
    args = parser.parse_args()
    build_path = args.pause_input_build.resolve()
    build = json.loads(build_path.read_text())
    validate(build_path, Path(build['rendererBuildPath']), Path(build['rendererGlProofPath']))
    keyboard_row = build['replacements']['mouse_keyboard_source.cpp.o']
    gamepad_row = build['replacements']['gamepad_source.cpp.o']
    manager_row = build['replacements']['input_manager.cpp.o']
    command = keyboard_row['compileCommand']
    assert command[-4:] == ['-c', keyboard_row['sourcePath'], '-o', keyboard_row['objectPath']]
    probe_path = Path(__file__).with_name('stock_pause_input_probe.cpp')
    output = Path(tempfile.mkdtemp(prefix='openshsm-pause-input-probe-', dir='/private/tmp'))
    pad_object = output / 'pad.cpp.o'
    pad_object.write_bytes(subprocess.check_output(
        ['/usr/bin/ar', '-p', build['archivePath'], 'pad.cpp.o']))
    imports = subprocess.check_output(['/usr/bin/nm', '-u', str(pad_object)], text=True)
    assert 'InputManager17get_wiimote_stateEi' in imports
    assert 'InputManager13consume_input' not in imports
    project = Path(__file__).resolve().parents[2]
    kpad_source = project / 'work/private-game/static-recomp/stock-baseline/window-input-sdk/output_44.cpp'
    kpad_text = kpad_source.read_text()
    bridge = Path(__file__).with_name('stock_input_sample_bridge.h')
    assert kpad_text.count('openshsm::experiment::forward_pc_kpad_read(ctx, false)') == 1
    assert kpad_text.count('openshsm::experiment::forward_pc_kpad_read(ctx, true)') == 1
    assert 'input.consume_input(0, snapshot)' in bridge.read_text()
    executable = output / 'probe'
    compile_command = [command[0], *command[1:-4], str(probe_path),
        keyboard_row['objectPath'], gamepad_row['objectPath'], manager_row['objectPath'],
        '-o', str(executable)]
    compiled = subprocess.run(compile_command, capture_output=True, text=True, timeout=180)
    (output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr[-4000:]
    tested = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
    assert tested.returncode == 0, tested.stderr
    assert 'PAUSE_INPUT_HEADLESS_PROBE_PASS 15' in tested.stdout
    report = {'result': 'PAUSE_INPUT_HEADLESS_SDL_PASS_NOT_GAME_VERIFIED',
        'pauseInputBuildPath': str(build_path), 'pauseInputBuildSha256': sha(build_path),
        'probePath': str(probe_path), 'probeSha256': sha(probe_path),
        'actualObjectPaths': [keyboard_row['objectPath'], gamepad_row['objectPath'], manager_row['objectPath']],
        'actualObjectSha256': [sha(keyboard_row['objectPath']), sha(gamepad_row['objectPath']),
            sha(manager_row['objectPath'])],
        'retainedPadObjectSha256': sha(pad_object),
        'retainedPadReadsCurrentState': True,
        'gameKpadSourcePath': str(kpad_source), 'gameKpadSourceSha256': sha(kpad_source),
        'snapshotBridgePath': str(bridge), 'snapshotBridgeSha256': sha(bridge),
        'executablePath': str(executable), 'executableSha256': sha(executable),
        'compileCommand': compile_command, 'output': tested.stdout.strip(),
        'dependencies': {str(path.resolve()): sha(path) for path in
            [Path(__file__), probe_path, build_path, kpad_source, bridge,
             Path(keyboard_row['objectPath']), Path(gamepad_row['objectPath']),
             Path(manager_row['objectPath'])]},
        'limits': ['Actual candidate keyboard/gamepad/manager objects and synthetic SDL states; no window or audio.',
            'Original game pause/skip, short-key delivery and visible menu remain unverified.']}
    path = output / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
