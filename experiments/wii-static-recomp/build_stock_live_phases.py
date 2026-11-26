"""Observe current main stages and reuse the original VI-path/movie observers, no pacing change."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_vi_path_observation import adapt_vi_path

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-live-phases'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-decoder-o3/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
command = list(parent['linkCommand'])
old_main = next(Path(arg) for arg in command if Path(arg).name == 'main.cpp.o')
original = old_main.with_suffix('')
text = original.read_text()
patches = [
    ('    openshsm::experiment::DebugOverlay debug_overlay;', '    openshsm::experiment::DebugOverlay debug_overlay;\n'
     '    openshsm::experiment::HostPhases host_phases;\n    extern uint64_t g_stat_frames;'),
    ('    while (!quit && ctx->is_running) {', '    while (!quit && ctx->is_running) {\n      host_phases.begin(g_stat_frames);'),
    ('      if (trace_startup) { startup_trace("input end"); }', '      if (trace_startup) { startup_trace("input end"); }\n      host_phases.mark(0);'),
    ('      if (trace_startup) { startup_trace("fifo begin"); }', '      host_phases.mark(1);\n      if (trace_startup) { startup_trace("fifo begin"); }'),
    ('      if (trace_startup) { startup_trace("fifo end"); }', '      if (trace_startup) { startup_trace("fifo end"); }\n      host_phases.mark(2);'),
    ('        if (trace_startup) { startup_trace("present begin"); }', '        host_phases.mark(3);\n        if (trace_startup) { startup_trace("present begin"); }'),
    ('        SDL_GL_SwapWindow(window);', '        host_phases.mark(4);\n        SDL_GL_SwapWindow(window);\n        host_phases.mark(5);'),
    ('      if (trace_startup) { startup_trace("audio end"); }', '      if (trace_startup) { startup_trace("audio end"); }\n      host_phases.mark(6);'),
    ('      ctx->vblank_pending = true;\n      std::this_thread::sleep_for(std::chrono::milliseconds(16));\n    }',
     '      host_phases.publication(ctx->vblank_pending.load(std::memory_order_relaxed));\n'
     '      ctx->vblank_pending = true;\n      host_phases.mark(7);\n'
     '      std::this_thread::sleep_for(std::chrono::milliseconds(16));\n'
     '      host_phases.mark(8);\n      host_phases.end(g_stat_frames);\n    }\n'
     '    host_phases.end(g_stat_frames, true);')]
for before, after in patches:
    assert text.count(before) == 1
    text = text.replace(before, after)
main_source, main_obj = output / 'main.cpp', output / 'main.cpp.o'
overlay = output / 'stock_debug_overlay.h'
overlay.write_bytes((original.parent / 'stock_debug_overlay.h').read_bytes())
main_source.write_text('#include "stock_host_phases.h"\n' + text)
main_arguments = json.loads((root / 'window-audio-callback/build.json').read_text())['arguments']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *main_arguments,
    '-I', str(original.parent), '-c', str(main_source), '-o', str(main_obj)], capture_output=True, text=True, timeout=180)
(output / 'main-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
old_vi = next(Path(arg) for arg in command if Path(arg).name == 'output_39.cpp.o')
vi_original = old_vi.with_suffix('')
vi_text, stages, calls = adapt_vi_path(vi_original.read_text())
vi_patches = [('token=%x vi=%x:%x:%x:%x', 'token=%x counter=%x vi=%x:%x:%x:%x'),
    ('ctx.gpr[31], ctx.msr, token,', 'ctx.gpr[31], ctx.msr, token, ctx.mmu.read32(0x8052AD4C),')]
for before, after in vi_patches:
    assert vi_text.count(before) == 1
    vi_text = vi_text.replace(before, after)
vi_source, vi_obj = output / 'output_39.cpp', output / 'output_39.cpp.o'
vi_source.write_text(vi_text)
compiled = json.loads((root / 'window-quantization/build.json').read_text())['compiled']
vi_arguments = next(row['arguments'] for row in compiled if row['source'] == 'output_39.cpp')
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *vi_arguments,
    '-I', str(vi_original.parent), '-c', str(vi_source), '-o', str(vi_obj)], capture_output=True, text=True, timeout=180)
(output / 'vi-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
command[command.index(str(old_main))] = str(main_obj)
command[command.index(str(old_vi))] = str(vi_obj)
exe = output / 'OpenSHSMStockLivePhases'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
inputs = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg not in (str(main_obj), str(vi_obj)):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        inputs[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({'result': 'CURRENT_HOST_VI_PHASES_BUILT_LIVE_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'mainOriginalPath': str(original), 'mainOriginalSha256': sha(original),
    'mainSourceSha256': sha(main_source), 'mainObjectSha256': sha(main_obj), 'patches': patches,
    'viOriginalPath': str(vi_original), 'viOriginalSha256': sha(vi_original), 'viSourceSha256': sha(vi_source),
    'viObjectSha256': sha(vi_obj), 'stages': stages, 'observedCalls': calls, 'viPatches': vi_patches,
    'linkCommand': command, 'executableSha256': sha(exe), 'retainedInputs': inputs,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_host_phases.h',
        public / 'stock_vi_path_observation.py', public / 'stock_movie_timing.h', overlay]},
    'limits': ['Main and guest39 observations only, original statements/arithmetic/clock/sleep unchanged.',
        'Host phase timestamps, sampled original VI milestones and already-linked movie boundary observer.',
        'pendingSamples is atomic state observation, not exact overwritten retrace count; timings include observer overhead.']}, indent=2) + '\n')
print('CURRENT_HOST_VI_PHASES_BUILT_LIVE_UNVERIFIED')
