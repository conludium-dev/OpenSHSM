"""Replace the existing window consumer only; exact runtime/75guest objects remain retained."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-audio-refill'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-adma-deadline/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
original = root / 'window-debug-overlay/main.cpp'
assert sha(original) == json.loads((root / 'window-debug-overlay/build.json').read_text())['sourceSha256']
before = '''        const auto queued_audio = SDL_GetQueuedAudioSize(audio_dev);
        if (queued_audio < 1024 * 4 * 2) {
          static int16_t abuf[1024 * 2];
          const auto supplied_audio = nwii::runtime::hw::dsp_audio_pull(abuf, 1024);
          const auto audio_result = SDL_QueueAudio(audio_dev, abuf, 1024 * 4);
          debug_overlay.audio(queued_audio, supplied_audio, true, audio_result != 0);
        } else {
          debug_overlay.audio(queued_audio, 0, false, false);
        }'''
after = '''        static openshsm::experiment::AudioRefillMonitor audio_refill_monitor;
        const auto refill = openshsm::experiment::refill_audio(
            [&] { return SDL_GetQueuedAudioSize(audio_dev); },
            [&](int16_t* samples, uint32_t frames) { return nwii::runtime::hw::dsp_audio_pull(samples, frames); },
            [&](const int16_t* samples, uint32_t frames) { return SDL_QueueAudio(audio_dev, samples, frames * 4); },
            [&](uint32_t queued, size_t supplied, bool pulled, bool failed, size_t requested) {
                debug_overlay.audio(queued, supplied, pulled, failed, requested);
            });
        audio_refill_monitor.record(refill);
        if (refill.errors) {
            std::cerr << "[AudioRefill] SDL queue failed: " << SDL_GetError() << '\\n';
            ctx->is_running = false;
            quit = true;
        }'''
text = original.read_text()
assert text.count(before) == 1
source, obj = output / 'main.cpp', output / 'main.cpp.o'
source.write_text('#include "stock_audio_refill.h"\n' + text.replace(before, after))
overlay_original = public / 'stock_debug_overlay.h'
overlay = output / 'stock_debug_overlay.h'
old_signature = 'void audio(uint32_t queued, size_t supplied, bool pulled, bool failed)'
overlay_patch = [(old_signature, old_signature[:-1] + ', size_t requested = 1024)'),
    ('short_pulls += supplied < 1024;', 'short_pulls += supplied < requested;')]
overlay_text = overlay_original.read_text()
for old, new in overlay_patch:
    assert overlay_text.count(old) == 1
    overlay_text = overlay_text.replace(old, new)
overlay.write_text(overlay_text)
arguments = json.loads((root / 'window-debug-overlay/build.json').read_text())['arguments']
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
command = list(parent['linkCommand'])
old_main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(old_main)] = str(obj)
exe = output / 'OpenSHSMStockAudioRefill'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'AUDIO_REFILL_BUILT_EXECUTION_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'archiveSha256': parent['archiveSha256'], 'linkCommand': command,
    'arguments': arguments, 'mainPatch': [before, after], 'overlayPatch': overlay_patch,
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_audio_refill.h',
        overlay_original, overlay, public / 'stock_test_profile_source.h', public / 'stock_test_ab_source.h']},
    'limits': ['Main consumer only,64ms target unchanged, max8pulls/4096frames per pass, no new mixer/buffer/thread.',
        'Queue only returned valid frames, partial/empty reports, strict SDL error handling; no zero-filled tail queued.',
        'All75guest/runtime/clock/scheduler/DSP/AI/graphics retained; verification/listening pending.']}, indent=2) + '\n')
print('AUDIO_REFILL_BUILT_EXECUTION_UNVERIFIED')
