"""Reproduce register-bank loss using actual FIFO replay and retained uniform code."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'tev-bank-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-sc-pc/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
renderer = root / 'window-quantization/renderer_gl.cpp'
records = json.loads((root / 'window-quantization/build.json').read_text())['compiled']
record = next(row for row in records if row['source'] == 'renderer_gl.cpp')
assert sha(renderer) == record['sourceSha256']
command = list(base['linkCommand'])
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
for name in ('renderer_gl.cpp', 'fifo_parser.cpp'):
    expected = (root / 'window-quantization' / (name + '.o')).read_bytes()
    assert subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name + '.o']) == expected
text = renderer.read_text()
start = text.index('  auto decode11 = ')
end = text.index('\n  static const bool s_tevtrace', start)
fragment = text[start:end]
source = output / 'retained-uniforms.cpp'
source.write_text('#include "runtime/gx_state.h"\nusing namespace nwii::runtime::gx;\n'
    'void stock_read_tev_uniforms(float* color, float* kcolor) {\n' + fragment + '\n}\n')
def run(cmd, log, cwd=None):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=180)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    return result.stdout

objects = []
for name, src in [('uniforms', source), ('probe', public / 'stock_tev_bank_probe.cpp')]:
    obj = output / (name + '.cpp.o')
    run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
        '-c', str(src), '-o', str(obj)], output / (name + '-compile.log'))
    objects.append(obj)
command[command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
command[1:1] = [str(obj) for obj in objects]
exe = output / 'bank-loss-probe'
command[command.index('-o') + 1] = str(exe)
run(command, output / 'link.log', root / 'export/build')
stdout = run([str(exe)], output / 'probe.log')
assert 'ACTUAL_FIFO_RENDER_UNIFORM_BANK_LOSS_REPRODUCED 8' in stdout
(output / 'verification.json').write_text(json.dumps({'result': 'ACTUAL_FIFO_RENDER_UNIFORM_BANK_LOSS_REPRODUCED8',
    'baseBuildSha256': sha(base_path), 'rendererSourceSha256': sha(renderer), 'archiveSha256': sha(archive),
    'extractedUniformSourceSha256': sha(source), 'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'),
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_tev_bank_probe.cpp']},
    'reference': 'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/VideoCommon/BPStructs.cpp',
    'limits': ['Synthetic BP sequences, four slots/both write orders, actual existing FIFO parser and BP replay.',
        'Uniform decoding is extracted byte-identically from linked renderer source, not actual GL uniform upload.',
        'No original SHSM FIFO trace, Wii hardware, shader pixel or purple-screen root-cause proof.',
        'No runtime fix or GXState ABI change in this diagnostic.']}, indent=2) + '\n')
print('ACTUAL_FIFO_RENDER_UNIFORM_BANK_LOSS_REPRODUCED8')
