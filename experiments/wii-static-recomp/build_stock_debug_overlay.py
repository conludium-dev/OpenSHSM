"""Private main-only FPS/audio overlay; preserve existing guest/runtime/render implementation."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-debug-overlay'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-test-profile/build.json'
parent = json.loads(parent_path.read_text())
for path, expected in {**parent['dependencies'], **parent['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
original = root / 'window-test-profile/main.cpp'
assert sha(original) == parent['sourceSha256']
text = original.read_text()
patches = [
    ('    bool quit = false;', '    bool quit = false;\n    openshsm::experiment::DebugOverlay debug_overlay;'),
    ('        SDL_GL_SwapWindow(window);', '        extern uint64_t g_stat_frames;\n'
        '        debug_overlay.draw(draw_w, draw_h, g_stat_frames);\n        SDL_GL_SwapWindow(window);'),
    ('        if (SDL_GetQueuedAudioSize(audio_dev) < 1024 * 4 * 2) {',
        '        const auto queued_audio = SDL_GetQueuedAudioSize(audio_dev);\n'
        '        if (queued_audio < 1024 * 4 * 2) {'),
    ('          nwii::runtime::hw::dsp_audio_pull(abuf, 1024);\n          SDL_QueueAudio(audio_dev, abuf, 1024 * 4);',
        '          const auto supplied_audio = nwii::runtime::hw::dsp_audio_pull(abuf, 1024);\n'
        '          const auto audio_result = SDL_QueueAudio(audio_dev, abuf, 1024 * 4);\n'
        '          debug_overlay.audio(queued_audio, supplied_audio, true, audio_result != 0);\n'
        '        } else {\n          debug_overlay.audio(queued_audio, 0, false, false);'),
    ('      if (audio_dev > 0) SDL_CloseAudioDevice(audio_dev);',
        '      debug_overlay.release();\n      if (audio_dev > 0) SDL_CloseAudioDevice(audio_dev);')]
for before, after in patches:
    assert text.count(before) == 1, before
    text = text.replace(before, after)
text = '#include "stock_debug_overlay.h"\n' + text
source, obj = output / 'main.cpp', output / 'main.cpp.o'
source.write_text(text)
arguments = parent['arguments']
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-4000:]
command = list(parent['linkCommand'])
command[command.index(str(original.with_suffix('.cpp.o')))] = str(obj)
exe = output / 'OpenSHSMStockDebugOverlay'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'PRIVATE_DEBUG_OVERLAY_BUILT_LIVE_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'archiveSha256': parent['archiveSha256'], 'linkCommand': command,
    'arguments': arguments, 'patches': patches,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_debug_overlay.h',
        public / 'stock_test_profile_source.h', public / 'stock_test_ab_source.h',
        root / 'input-snapshot-research/include/input/input_manager.h']},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['Opt-in overlay after final blit on default framebuffer, no original EFB/guest state edits.',
        'GX FPS counts existing consumed render batches; output FPS counts window presents, not original game speed percent.',
        'Audio supply observed, calls/queued buffer unchanged; debug/GPU capture overhead present.']}, indent=2) + '\n')
print('PRIVATE_DEBUG_OVERLAY_BUILT_LIVE_UNVERIFIED')
