"""Real GL overlay isolation/state/pixel test, not whole-game FPS acceptance."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-debug-overlay'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
source, obj = public / 'stock_debug_overlay_probe.cpp', output / 'probe.cpp.o'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
assert compiled.returncode == 0, compiled.stderr[-3000:]
command = list(build['linkCommand'])
command[command.index(str(output / 'main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'overlay-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
assert 'DEBUG_OVERLAY_GL_STATE_EFB_PRESERVED' in result.stdout
(output / 'component-verification.json').write_text(json.dumps({
    'result': 'DEBUG_OVERLAY_GL_STATE_EFB_PRESERVED', 'buildSha256': sha(build_path),
    'probeSourceSha256': sha(source), 'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'),
    'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Actual hidden GL context: original FBO pixels/GL bindings/viewport/scissor/mask/enables/clear/point size preserved.',
        'Rendered white glyph pixel verified, no GL error; synthetic graphics isolation, not original game speed.']}, indent=2) + '\n')
print(result.stdout.strip())
