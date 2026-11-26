"""Actual integrated DSP/AI/MMIO/SDK/event/SDL conversion fixture; not physical Wii audio proof."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-adma-chunks'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
parent = json.loads((root / 'window-debug-overlay/build.json').read_text())
source, obj = public / 'stock_adma_chunks_probe.cpp', output / 'probe.cpp.o'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *parent['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
assert compiled.returncode == 0, compiled.stderr[-3000:]
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'chunk-probe'
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
log = output / 'probe.log'
log.write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'ADMA_CHUNKS_SDK_PCM_IRQ_RATE_PASS' in result.stdout, (result.returncode, result.stdout, result.stderr)
(output / 'component-verification.json').write_text(json.dumps({'result': 'ADMA_CHUNKS_SDK_PCM_IRQ_RATE_PASS',
    'buildSha256': sha(build_path), 'sourceSha256': sha(source), 'executableSha256': sha(exe),
    'logSha256': sha(log), 'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Actual integrated backend+retained original SDK, chunk ordering/count/startIRQ/boundary/late reprogram/stop/reset.',
        '32k PCM exact,6000native48kchunks compared with direct SDL reference at identical8-frame input granularity.',
        'Bulk SDL control initially dropped512tail frames, two-part bulk had5tail sample differences; no partition-invariance claim.',
        'Manual virtual TB, emulator heuristic startup17ticks, no actual audio device/pacing/hardware acceptance.']}, indent=2) + '\n')
print(result.stdout.strip())
