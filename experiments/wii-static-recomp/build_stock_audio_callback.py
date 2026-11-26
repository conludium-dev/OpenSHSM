"""Replace only main audio servicing on the current PC-boot candidate; original producer/guests retained."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-audio-callback'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-pc-boot/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in parent['retainedInputs'].items():
    assert sha(Path(path)) == digest
original = root / 'window-audio-refill/main.cpp'
base = json.loads((root / 'window-audio-refill/build.json').read_text())
assert sha(original) == base['sourceSha256']
text = original.read_text()
start = text.index('        static openshsm::experiment::AudioRefillMonitor audio_refill_monitor;')
end = text.index('\n      }', start)
audio_before = text[start:end]
patches = [('#include "stock_audio_refill.h"', '#include "stock_audio_callback.h"'),
    ('  SDL_AudioDeviceID audio_dev = 0;', '  SDL_AudioDeviceID audio_dev = 0;\n'
     '  openshsm::experiment::AudioCallback audio_callback(nwii::runtime::hw::dsp_audio_pull);\n'
     '  struct AudioDeviceGuard {\n'
     '    SDL_AudioDeviceID& device;\n'
     '    ~AudioDeviceGuard() { if (device) { SDL_CloseAudioDevice(device); } }\n'
     '  } audio_device_guard{audio_dev};'),
    ('    want.samples = 1024;', '    want.samples = 1024;\n'
     '    want.callback = openshsm::experiment::AudioCallback::render;\n'
     '    want.userdata = &audio_callback;'),
    ('    if (audio_dev > 0) SDL_PauseAudioDevice(audio_dev, 0);', ''),
    ('  std::thread cpu_thread(cpu_thread_func, ctx.get());',
     '  std::thread cpu_thread(cpu_thread_func, ctx.get());\n'
     '  if (audio_dev) { SDL_PauseAudioDevice(audio_dev, 0); }'),
    (audio_before, '        const auto stats = audio_callback.snapshot();\n'
     '        debug_overlay.callback_audio(stats.calls, stats.supplied, stats.short_calls, stats.errors);\n'
     '        audio_callback.report();\n'
     '        if (stats.errors) { ctx->is_running = false; quit = true; }'),
    ('      if (audio_dev > 0) SDL_CloseAudioDevice(audio_dev);',
     '      if (audio_dev) {\n'
     '          SDL_CloseAudioDevice(audio_dev);\n'
     '          audio_dev = 0;\n'
     '          audio_callback.report(true);\n'
     '      }')]
for before, after in patches:
    assert text.count(before) == 1
    text = text.replace(before, after)
source, obj = output / 'main.cpp', output / 'main.cpp.o'
source.write_text(text)
overlay_base = public / 'stock_debug_overlay.h'
overlay_text = overlay_base.read_text()
method = '''    void callback_audio(uint64_t calls, uint64_t supplied, uint64_t shorts, uint64_t failed) {
        pulls += calls - callback_calls;
        supplied_frames += supplied - callback_supplied;
        short_pulls += shorts - callback_shorts;
        errors += failed - callback_errors;
        callback_calls = calls;
        callback_supplied = supplied;
        callback_shorts = shorts;
        callback_errors = failed;
    }

'''
overlay_patches = [('    void audio(', method + '    void audio('),
    ('"AUDIO MIN %.1F MS  SHORT %llu", queue_ms,', '"AUDIO CALLBACK SHORT %llu",'),
    ('    uint32_t min_queue = UINT32_MAX;', '    uint64_t callback_calls = 0, callback_supplied = 0, callback_shorts = 0, callback_errors = 0;\n    uint32_t min_queue = UINT32_MAX;')]
for before, after in overlay_patches:
    assert overlay_text.count(before) == 1
    overlay_text = overlay_text.replace(before, after)
overlay = output / 'stock_debug_overlay.h'
overlay.write_text(overlay_text)
arguments = base['arguments']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = list(parent['linkCommand'])
old_main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(old_main)] = str(obj)
exe = output / 'OpenSHSMStockAudioCallback'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'AUDIO_CALLBACK_BUILT_EXECUTION_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'arguments': arguments, 'linkCommand': command, 'patches': patches,
    'overlayPatches': overlay_patches, 'originalPath': str(original), 'originalSha256': sha(original),
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_audio_callback.h', overlay_base, overlay]},
    'retainedInputs': {path: digest for path, digest in parent['retainedInputs'].items() if path != old_main} |
        {str(root / 'window-pc-boot/output_18.cpp.o'): sha(root / 'window-pc-boot/output_18.cpp.o')},
    'limits': ['Main consumer only, existing SDL device callback/1024frames/32kS16stereo, no extra ring/service/thread.',
        'DSP producer/mutex/runtime and75guests including opt-in PC boot skip retained.',
        'No GL/guest context/queue operations in callback; shortage is silence explicitly counted, not source samples.',
        'Callbacks start after runtime/context setup; device closes before callback userdata expires.']}, indent=2) + '\n')
print('AUDIO_CALLBACK_BUILT_EXECUTION_UNVERIFIED')
