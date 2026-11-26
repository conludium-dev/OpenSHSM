"""Run existing FIFO/drain/renderer through real GL, forwarding the actual completion fence."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-pe-execute'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
native_path = output / 'execution-verification.json'
native = json.loads(native_path.read_text())
assert native['buildSha256'] == sha(build_path)
assert native['result'] == 'PE_PARSE_NO_ACK_ORDERED_APPLY5_PREFIX_BOUNDS7_VERIFIED'
assert sha(Path(build['archivePath'])) == build['archiveSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-pe-gpu-tests-', dir='/private/tmp'))
probe = Path('experiments/wii-static-recomp/stock_pe_gpu_pipeline_probe.cpp').resolve()
obj = cache / 'probe.cpp.o'
flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']['37']['arguments']
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags, '-UNDEBUG', '-c', str(probe), '-o', str(obj)]
compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
link = list(build['linkCommand'])
main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
link.insert(1, str(obj))
exe = cache / 'pe-gpu-probe'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=60)
assert run.returncode == 0 and 'ACTUAL_FIFO_RENDER_REAL_GL_FENCE_BEFORE_PE_ACK_PASS6' in run.stdout, run.stdout + run.stderr
(output / 'gpu-pipeline-verification.json').write_text(json.dumps({
    'result': 'ACTUAL_FIFO_RENDER_REAL_GL_FENCE_BEFORE_PE_ACK_PASS6', 'buildSha256': sha(build_path),
    'nativeProofSha256': sha(native_path), 'verifierSha256': sha(Path(__file__)), 'probeSha256': sha(probe),
    'compileCommand': command, 'linkCommand': link, 'executablePath': str(exe), 'executableSha256': sha(exe),
    'stdout': run.stdout, 'stderr': run.stderr,
    'limits': ['Existing FIFO queue/drain/Renderer executes finish/token-only, partial BP retained, negative prefix and multiple completion markers.',
        'Instrumented GL loader function forwards real glFinish; validates previous GPU clear pixel and PE state before returning fence.',
        'No mocked renderer/GPU, but preceding original textured DrawPrimitive and guest original wait-loop execution not covered.',
        'Full texture/CPU/frame/timer/live coherence/performance and promotion pending.']}, indent=2) + '\n')
print('ACTUAL_FIFO_RENDER_REAL_GL_FENCE_BEFORE_PE_ACK_PASS6')
print(run.stdout)
