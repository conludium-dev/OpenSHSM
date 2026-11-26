"""Validate consumer with poisoned unused tails, queue bounds and errors; not physical device acceptance."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-audio-refill'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
source = public / 'stock_audio_refill_probe.cpp'
exe = output / 'refill-probe'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
    '-I', str(public), str(source), '-o', str(exe)], capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
log = output / 'probe.log'
log.write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'AUDIO_REFILL_VALID_PCM_CAP_BOUNDS_ERRORS_PASS9' in result.stdout
(output / 'component-verification.json').write_text(json.dumps({'result': 'AUDIO_REFILL_VALID_PCM_CAP_BOUNDS_ERRORS_PASS9',
    'buildSha256': sha(build_path), 'sourceSha256': sha(source), 'executableSha256': sha(exe),
    'logSha256': sha(log), 'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['9controlled callback fixtures, poisoned unused tail never queued, valid sample order preserved.',
        'Existing64ms target/partial-full-empty/backlog/failure/max8pulls4096frames bounds.',
        'Synthetic queue adapter; actual DSP/MMIO/frame/balance/SDL device/human listening acceptance separate.']}, indent=2) + '\n')
print(result.stdout.strip())
