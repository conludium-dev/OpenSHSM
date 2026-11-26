"""Build a hidden real-driver pixel fixture for corrected TEV bank uniforms."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-tev-banks'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = output / 'build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
assert sha(output / 'include/runtime/gx_state.h') == base['gxHeaderSha256']
assert sha(output / 'libnwiiruntime.a') == base['archiveSha256']
record = next(row for row in base['compiled'] if row['member'] == 'renderer_gl.cpp.o')
source, obj = public / 'stock_tev_bank_pixel_probe.cpp', output / 'pixel-probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'pixel-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = list(base['linkCommand'])
command[command.index(str(output / 'main.cpp.o'))] = str(output / 'contract-entry.cpp.o')
command[1:1] = [str(obj), str(output / 'uniforms.cpp.o')]
exe = output / 'pixel-probe'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'pixel-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'pixel-build.json').write_text(json.dumps({'result': 'TEV_BANK_PIXEL_FIXTURE_BUILT_EXECUTION_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'executableSha256': sha(exe),
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), source]},
    'limits': ['Real-driver fixture must still execute; direct fixture GL uniform upload uses extracted actual decoder.',
        'Synthetic one-stage TEV, not full existing renderer draw/presentation or original SHSM frame.']}, indent=2) + '\n')
print('TEV_BANK_PIXEL_FIXTURE_BUILT_EXECUTION_UNVERIFIED', exe)
