"""Own-Wii PC play without a deadline, retaining bounded launch/crash logs."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from stock_first_image_patch import restore as restore_first_image
from verify_wii_us_copy import audit_copy


class BoundedCapture:
    def __init__(self, prefix, tail, prefix_limit=8 * 1024 * 1024, tail_limit=256 * 1024):
        self.prefix = prefix
        self.tail = tail
        self.prefix_limit = prefix_limit
        self.tail_limit = tail_limit
        self.total = 0
        self.written = 0
        self.recent = bytearray()
        self.last_tail_flush = time.monotonic()

    def feed(self, chunk):
        self.total += len(chunk)
        part = chunk[:max(0, self.prefix_limit - self.written)]
        self.prefix.write(part)
        self.prefix.flush()
        self.written += len(part)
        self.recent.extend(chunk)
        if len(self.recent) > self.tail_limit:
            del self.recent[:-self.tail_limit]
        now = time.monotonic()
        if now - self.last_tail_flush >= 1.0:
            self.finish()
            self.last_tail_flush = now

    def finish(self):
        self.tail.seek(0)
        self.tail.write(self.recent)
        self.tail.truncate()
        self.tail.flush()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def play_command(executable, game, config):
    return [str(executable), str(game), str(config)]


def active_game_commands(processes, game):
    matches = []
    for line in processes.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        command = parts[1]
        executable = command.split(None, 1)[0]
        if Path(executable).name.startswith('OpenSHSM') and str(game) in command:
            matches.append(line)
    return matches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--game-data', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--paired-build', type=Path)
    parser.add_argument('--psq-build', type=Path)
    parser.add_argument('--interpreter-build', type=Path)
    parser.add_argument('--sysconf-build', type=Path)
    parser.add_argument('--dsp-capture-build', type=Path)
    parser.add_argument('--font-build', type=Path)
    parser.add_argument('--ax-build', type=Path)
    parser.add_argument('--renderer-build', type=Path)
    parser.add_argument('--renderer-gl-proof', type=Path)
    parser.add_argument('--pause-input-build', type=Path)
    parser.add_argument('--capture-renderer', action='store_true')
    parser.add_argument('--capture-font', action='store_true')
    parser.add_argument('--capture-startup', action='store_true')
    args = parser.parse_args()
    assert not (args.capture_startup and args.capture_renderer), 'Choose one framebuffer capture mode.'
    project = Path(__file__).resolve().parents[2]
    root = project / 'work/private-game/static-recomp/stock-baseline'
    path = args.build.resolve()
    build = json.loads(path.read_text())
    assert build['result'] == 'PC_BRANDING_MAIN_ONLY_COMPILED_LINKED_NOT_LIVE_VERIFIED'
    assert build['version'] == '0.0.42' and build['windowTitle'] == 'OpenSHSM BUILD 0.0.42'
    assert path.parent.parent == Path('/private/tmp') and path.parent.name.startswith('openshsm-pc-branding-')
    for file, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(file) == digest, file
    source = Path(build['sourcePath']).read_text()
    if build.get('firstImage', False):
        assert sha(path.parent / 'stock_first_image.h') == sha(Path(__file__).resolve().parent / 'stock_first_image.h')
        source = restore_first_image(source)
    before = 'SDL_CreateWindow("NWiiRecomp",'
    after = 'SDL_CreateWindow(OPENSHSM_RECOMP_WINDOW_TITLE,'
    assert source.count(after) == 1
    assert args.capture_startup == bool(build.get('startupCapture', False))
    if args.capture_startup:
        capture_after = 'if (++shot_frame <= 15 || (shot_frame <= 1200 && (shot_frame % 15) == 0)) {'
        assert source.count(capture_after) == 1
        source = source.replace(capture_after, 'if ((++shot_frame % 300) == 0) {', 1)
    assert source.removeprefix('#include "BuildVersion.h"\n').replace(after, before, 1) == Path(build['originalSourcePath']).read_text()
    assert source.count('const char *config_path = (argc >= 3) ? argv[2] : "config.toml";') == 1
    assert sha(build['sourcePath']) == build['sourceSha256']
    assert sha(build['objectPath']) == build['objectSha256']
    assert sha(path.parent / 'BuildVersion.h') == sha(Path(__file__).resolve().parent / 'BuildVersion.h')
    parent_path = Path(build['parentBuildPath'])
    assert sha(parent_path) == build['parentBuildSha256']
    component = json.loads((parent_path.parent / 'component-verification.json').read_text())
    assert component['buildSha256'] == sha(parent_path)
    assert component['result'] == 'BP_ORDER_NATIVE_SHADER_GPU_PIPELINE_RETAINED_PARENT_VERIFIED'
    exe = Path(build['executablePath']).resolve()
    assert exe.parent == path.parent and exe.name == 'OpenSHSM-0.0.42'
    assert sha(exe) == build['executableSha256']
    assert b'OpenSHSM BUILD 0.0.42\0' in exe.read_bytes()
    game_audit = audit_copy(args.game_data) if args.game_data else None
    game = Path(game_audit['source']) if game_audit else project / 'work/private-game/disc/DATA'
    dol = game / 'sys/main.dol'
    assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
    paired_path = args.paired_build.resolve() if args.paired_build else None
    if paired_path:
        from stock_paired_build_validation import validate
        exe = validate(paired_path, path, build)
    psq_path = args.psq_build.resolve() if args.psq_build else None
    psq_relocated_path = None
    if psq_path:
        assert paired_path, 'PSQ derivative requires its verified paired parent.'
        from stock_relocation_build_metadata import psq as relocate_psq
        from stock_psq_float_build import validate as validate_psq
        psq_relocated_path = relocate_psq(psq_path, paired_path, root)
        exe = validate_psq(psq_relocated_path, paired_path, json.loads(paired_path.read_text()))
    interpreter_path = args.interpreter_build.resolve() if args.interpreter_build else None
    if interpreter_path:
        assert psq_path, 'Fallback derivative requires its verified current PSQ parent.'
        from stock_interpreter_reached_build import validate as validate_interpreter
        exe = validate_interpreter(interpreter_path, psq_path, json.loads(psq_path.read_text()))
    sysconf_path = args.sysconf_build.resolve() if args.sysconf_build else None
    sysconf_relocated_path = None
    if sysconf_path:
        assert interpreter_path, 'SYSCONF derivative requires the verified current fallback parent.'
        from stock_relocation_build_metadata import sysconf as relocate_sysconf
        from stock_sysconf_build import validate as validate_sysconf
        sysconf_relocated_path = relocate_sysconf(sysconf_path, interpreter_path, root)
        exe = validate_sysconf(sysconf_relocated_path, interpreter_path, json.loads(interpreter_path.read_text()))
    dsp_capture_path = args.dsp_capture_build.resolve() if args.dsp_capture_build else None
    if dsp_capture_path:
        assert sysconf_path, 'DSP capture requires the verified current SYSCONF parent.'
        from stock_dsp_capture_build import validate as validate_dsp_capture
        exe = validate_dsp_capture(dsp_capture_path, sysconf_path, json.loads(sysconf_path.read_text()))
    font_path = args.font_build.resolve() if args.font_build else None
    assert not args.capture_font or font_path, 'Font capture requires the current font derivative.'
    if font_path:
        assert dsp_capture_path, 'Font derivative requires the verified current DSP parent.'
        from stock_debug_font_build import validate as validate_font
        exe = validate_font(font_path, dsp_capture_path, json.loads(dsp_capture_path.read_text()))
    ax_path = args.ax_build.resolve() if args.ax_build else None
    if ax_path:
        assert font_path and dsp_capture_path, 'AX mixer requires the current verified font/DSP chain.'
        from stock_axwii_device_build import validate as validate_ax
        exe = validate_ax(ax_path, font_path, json.loads(font_path.read_text()), dsp_capture_path)
    renderer_path = args.renderer_build.resolve() if args.renderer_build else None
    gl_proof_path = args.renderer_gl_proof.resolve() if args.renderer_gl_proof else None
    assert bool(renderer_path) == bool(gl_proof_path), 'Renderer derivative requires its hidden GL proof.'
    assert not args.capture_renderer or renderer_path, 'Renderer capture requires its verified derivative.'
    if renderer_path:
        assert ax_path, 'Renderer derivative requires the verified current AX parent.'
        from stock_gx_renderer_texgen_validation import validate as validate_renderer
        exe = validate_renderer(renderer_path, ax_path, gl_proof_path)
    pause_input_path = args.pause_input_build.resolve() if args.pause_input_build else None
    if pause_input_path:
        assert renderer_path and gl_proof_path, 'Pause-input derivative requires the verified renderer and GL proof.'
        from stock_pause_input_validation import validate as validate_pause_input
        exe = validate_pause_input(pause_input_path, renderer_path, gl_proof_path)
    config = args.config.resolve() if args.config else root / 'user/config.toml'
    assert config.exists(), 'Existing user config required; no reset or implicit creation.'
    run_dir = args.run_dir.resolve() if args.run_dir else root / 'user'
    assert run_dir.is_dir(), 'Existing run directory required; no implicit creation.'
    processes = subprocess.check_output(['/bin/ps', '-axo', 'pid=,command='], text=True)
    active = active_game_commands(processes, game)
    assert not active, 'Existing game instance: ' + repr(active)
    env = {key: value for key, value in os.environ.items()
        if not key.startswith(('NWII_', 'SHSM_')) and key not in ('OPENSHSM_DSP_CAPTURE_DIR', 'OPENSHSM_DEBUG_CAPTURE', 'OPENSHSM_AXWII_MIXER')}
    env.update(NWII_HEADLESS='0', NWII_DEBUG_OVERLAY='1', NWII_WALLTB='1', NWII_SKIP_BOOT_NOTICES='1')
    if ax_path:
        env['OPENSHSM_AXWII_MIXER'] = '1'
    output = Path(tempfile.mkdtemp(prefix='openshsm-pc-play-', dir='/private/tmp'))
    if args.capture_font:
        env['OPENSHSM_DEBUG_CAPTURE'] = str(output / 'font')
    if dsp_capture_path:
        capture_directory = output / 'private-dsp-capture'
        capture_directory.mkdir(mode=0o700)
        env['OPENSHSM_DSP_CAPTURE_DIR'] = str(capture_directory)
    if args.capture_startup:
        env['NWII_SCREENSHOT'] = str(output / 'startup')
    if args.capture_renderer:
        env['NWII_SCREENSHOT'] = str(output / 'renderer')
    record = {'result': 'USER_PLAY_RUNNING_WITHOUT_DEADLINE', 'deadlineEnabled': False,
        'argv': play_command(exe, game, config),
        'startupCapture': args.capture_startup,
        'rendererCapture': args.capture_renderer,
        'fontCapture': args.capture_font,
        'buildPath': str(path), 'buildSha256': sha(path), 'executableSha256': sha(exe),
        'pairedBuildPath': str(paired_path) if paired_path else None,
        'pairedBuildSha256': sha(paired_path) if paired_path else None,
        'psqBuildPath': str(psq_path) if psq_path else None,
        'psqBuildSha256': sha(psq_path) if psq_path else None,
        'psqRelocatedProofPath': str(psq_relocated_path) if psq_relocated_path else None,
        'psqRelocatedProofSha256': sha(psq_relocated_path) if psq_relocated_path else None,
        'interpreterBuildPath': str(interpreter_path) if interpreter_path else None,
        'interpreterBuildSha256': sha(interpreter_path) if interpreter_path else None,
        'sysconfBuildPath': str(sysconf_path) if sysconf_path else None,
        'sysconfBuildSha256': sha(sysconf_path) if sysconf_path else None,
        'sysconfRelocatedProofPath': str(sysconf_relocated_path) if sysconf_relocated_path else None,
        'sysconfRelocatedProofSha256': sha(sysconf_relocated_path) if sysconf_relocated_path else None,
        'dspCaptureBuildPath': str(dsp_capture_path) if dsp_capture_path else None,
        'dspCaptureBuildSha256': sha(dsp_capture_path) if dsp_capture_path else None,
        'fontBuildPath': str(font_path) if font_path else None,
        'fontBuildSha256': sha(font_path) if font_path else None,
        'axBuildPath': str(ax_path) if ax_path else None,
        'axBuildSha256': sha(ax_path) if ax_path else None,
        'rendererBuildPath': str(renderer_path) if renderer_path else None,
        'rendererBuildSha256': sha(renderer_path) if renderer_path else None,
        'rendererGlProofPath': str(gl_proof_path) if gl_proof_path else None,
        'rendererGlProofSha256': sha(gl_proof_path) if gl_proof_path else None,
        'pauseInputBuildPath': str(pause_input_path) if pause_input_path else None,
        'pauseInputBuildSha256': sha(pause_input_path) if pause_input_path else None,
        'configPath': str(config), 'configSha256AtLaunch': sha(config),
        'runDirectory': str(run_dir), 'dolSha256': sha(dol),
        'gameDataAudit': game_audit,
        'startedUnix': time.time(), 'limits': ['No automated input/focus or config/save reset.',
            'Logs capped at 8MiB prefix plus 256KiB final tail; cap never stops the game.',
            'Renderer capture, when selected, writes game-owned BMP frames every 300 presents.',
            'CPU/audio may end intentionally with exit0; inspect logs, not only process status.',
            'No live mouse/keyboard/crash/performance acceptance is implied by launch.']}
    with (output / 'runtime-prefix.log').open('wb') as prefix, (output / 'runtime-tail.log').open('wb') as tail:
        child = subprocess.Popen(play_command(exe, game, config), cwd=run_dir,
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True)
        record['pid'] = child.pid
        report = output / 'result.json'
        report.write_text(json.dumps(record, indent=2) + '\n')
        print('USER_PLAY_NO_DEADLINE', child.pid, output, flush=True)
        capture = BoundedCapture(prefix, tail)
        while True:
            chunk = child.stdout.read1(65536)
            if not chunk:
                break
            capture.feed(chunk)
        capture.finish()
        record.update(result='USER_PLAY_EXITED', exitCode=child.wait(), endedUnix=time.time(),
            logBytesReceived=capture.total, logPrefixBytes=capture.written,
            logTailBytes=len(capture.recent), configSha256AtExit=sha(config))
        report.write_text(json.dumps(record, indent=2) + '\n')
        print('USER_PLAY_EXITED', record['exitCode'], report, flush=True)


if __name__ == '__main__':
    main()
