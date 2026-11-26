"""Remove only the extra GUI-generated VI request; keep the existing runtime periodic source unchanged."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-vi-timer'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-live-phases/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
original = root / 'window-live-phases/main.cpp'
assert sha(original) == parent['mainSourceSha256']
text = original.read_text()
before = '''      host_phases.publication(ctx->vblank_pending.load(std::memory_order_relaxed));
      ctx->vblank_pending = true;'''
assert text.count(before) == 1
source, obj = output / 'main.cpp', output / 'main.cpp.o'
source.write_text(text.replace(before, ''))
overlay = output / 'stock_debug_overlay.h'
overlay.write_bytes((original.parent / 'stock_debug_overlay.h').read_bytes())
arguments = json.loads((root / 'window-audio-callback/build.json').read_text())['arguments']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
command = list(parent['linkCommand'])
command[command.index(str(original) + '.o')] = str(obj)
exe = output / 'OpenSHSMStockVITimer'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
inputs = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg != str(obj):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        inputs[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({'result': 'EXISTING_VI_TIMER_ONLY_BUILT_LIVE_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'mainOriginalPath': str(original), 'mainOriginalSha256': sha(original),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'executableSha256': sha(exe),
    'patch': [before, ''], 'linkCommand': command, 'retainedInputs': inputs,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), overlay,
        Path('experiments/wii-static-recomp/stock_host_phases.h').resolve()]},
    'limits': ['Main only: GUI no longer writes vblank_pending, existing scheduler60Hz and allruntime/75guests retained.',
        'No new timer/thread/queue, no timebase/FPS cap/IRQ status/guest readiness force or original asset change.',
        'Experimental PC timing adaptation; scheduled VI has original existing gating/coalescing limitations.',
        'No physical Wii beam/region timing or all-game/controller/sound acceptance.']}, indent=2) + '\n')
print('EXISTING_VI_TIMER_ONLY_BUILT_LIVE_UNVERIFIED')
