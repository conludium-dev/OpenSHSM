"""Measure host window startup using retained CP-enabled runtime and guest objects."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shlex
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--warmup', action='store_true')
parser.add_argument('--presentation-trace', action='store_true')
parser.add_argument('--software-present', action='store_true')
args = parser.parse_args()
assert not args.software_present or args.presentation_trace
assert not (args.software_present and args.warmup)
project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
build = root / 'export/build'
base = root / 'ipc-cpbp'
variant = 'window-paced' if args.software_present else 'window-warm' if args.warmup else 'window-present' if args.presentation_trace else 'window-trace'
output = root / variant
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((base / 'build.json').read_text())
archive = base / 'libnwiiruntime.a'
assert sha(archive) == manifest['archiveSha256']
original = root / 'export/nWiiRuntime/src/core/main.cpp'
text = original.read_text()
anchor = '  ctx->tb_start = std::chrono::steady_clock::now();'
assert text.count(anchor) == 1
instrumentation = '''  const auto startup_origin = std::chrono::steady_clock::now();
  auto startup_trace = [&](const char* phase) {
      auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
          std::chrono::steady_clock::now() - startup_origin).count();
      std::cerr << "[WindowStartup] us=" << elapsed << " phase=" << phase << std::endl;
  };
'''
if args.warmup:
    instrumentation += '''  if (!headless) {
      startup_trace("warmup begin");
      SDL_PumpEvents();
      startup_trace("warmup end");
  }
'''
text = text.replace(anchor, instrumentation + anchor)
text = text.replace('  std::thread cpu_thread(cpu_thread_func, ctx.get());',
    '  startup_trace("cpu launch");\n  std::thread cpu_thread(cpu_thread_func, ctx.get());')
anchor = '    while (!quit && ctx->is_running) {'
assert text.count(anchor) == 1
prefix, suffix = text.split(anchor)
suffix = '''
      static int startup_ticks = 0;
      bool trace_startup = ++startup_ticks <= 3;
      if (trace_startup) { startup_trace("loop begin"); }
''' + suffix
suffix = suffix.replace('        while (SDL_PollEvent(&e)) {',
    '        if (trace_startup) { startup_trace("poll begin"); }\n        while (SDL_PollEvent(&e)) {', 1)
suffix = suffix.replace('      nwii::runtime::input::InputManager::get().update();',
    '      if (trace_startup) { startup_trace("poll end/input begin"); }\n      nwii::runtime::input::InputManager::get().update();\n      if (trace_startup) { startup_trace("input end"); }', 1)
suffix = suffix.replace('      ProcessGXFifo();',
    '      if (trace_startup) { startup_trace("fifo begin"); }\n      ProcessGXFifo();\n      if (trace_startup) { startup_trace("fifo end"); }', 1)
text = prefix + anchor + suffix
if args.presentation_trace:
    traces = [
        ('        glBindFramebuffer(GL_FRAMEBUFFER, 0);\n        int draw_w', '        if (trace_startup) { startup_trace("present begin"); }\n        glBindFramebuffer(GL_FRAMEBUFFER, 0);\n        int draw_w'),
        ('        glBlitFramebuffer(0, 0, 640, 480, 0, 0, draw_w, draw_h,', '        if (trace_startup) { startup_trace("blit begin"); }\n        glBlitFramebuffer(0, 0, 640, 480, 0, 0, draw_w, draw_h,'),
        ('        if (const char *shot_pfx', '        if (trace_startup) { startup_trace("blit end"); }\n        if (const char *shot_pfx'),
        ('        SDL_GL_SwapWindow(window);', '        if (trace_startup) { startup_trace("swap begin"); }\n        SDL_GL_SwapWindow(window);\n        if (trace_startup) { startup_trace("swap end"); }'),
        ('      if (audio_dev > 0) {', '      if (trace_startup) { startup_trace("audio begin"); }\n      if (audio_dev > 0) {'),
        ('      ctx->vblank_pending = true;\n      if (headless)', '      if (trace_startup) { startup_trace("audio end"); }\n      ctx->vblank_pending = true;\n      if (headless)'),
    ]
    for old, new in traces:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
source = output / 'main.cpp'
if args.software_present:
    old = '      SDL_GL_SetSwapInterval(1);'
    assert text.count(old) == 1
    text = text.replace(old, '      SDL_GL_SetSwapInterval(0);')
    old = '      if (headless) std::this_thread::sleep_for(std::chrono::milliseconds(16));'
    assert text.count(old) == 1
    text = text.replace(old, '      std::this_thread::sleep_for(std::chrono::milliseconds(16));')
source.write_text(text)
flags = (build / 'CMakeFiles/OpenSHSMStockBaseline.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
obj = output / 'main.cpp.o'
result = subprocess.run([compiler, *arguments, '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
entry = 'CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o'
assert command.count(entry) == 1
retained = {item: sha(build / item) for item in command if item.endswith('.cpp.o') and item != entry}
command[command.index(entry)] = str(obj)
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
exe = output / {'window-paced': 'OpenSHSMStockWindowPaced', 'window-warm': 'OpenSHSMStockWindowWarm', 'window-present': 'OpenSHSMStockWindowPresent', 'window-trace': 'OpenSHSMStockWindowTrace'}[variant]
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
(output / 'build.json').write_text(json.dumps({
    'result': 'WINDOW_STARTUP_VARIANT_BUILT', 'warmup': args.warmup, 'presentationTrace': args.presentation_trace,
    'softwarePresent': args.software_present,
    'sourceSha256': sha(source), 'baseSourceSha256': sha(original),
    'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'retainedObjects': retained,
    'limits': ['Host timing diagnostics; optional SDL event pump before original guest timebase initialization.',
        'No guest watchdog/deadline, ready flags, callbacks, GPU state or original resources changed.']
}, indent=2) + '\n')
print('Window startup build;', len(retained), 'guest/dispatcher objects and full CP-enabled runtime retained')
