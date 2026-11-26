"""Check snapshot format and guest-state nonmutation; synthetic fixture, not Wii save-state."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-thp-snapshot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = output / 'build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
source, obj = public / 'stock_thp_snapshot_probe.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
command = list(base['linkCommand'])
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'snapshot-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
directory = Path(tempfile.mkdtemp(prefix='component-', dir=output))
capture = directory / 'snapshot.bin'
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
result = subprocess.run([str(exe), str(capture)], env=dict(env, NWII_THP_SNAPSHOT=str(capture)),
    capture_output=True, text=True, timeout=30)
(directory / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
assert result.stderr.count('[THPSnapshot] saved=1') == 1
assert capture.stat().st_size == 8 + 128 + 256 + 256 + 32 + 16 + 32 + 48 + 8 + 24 + (88 * 1024 * 1024 + 256 * 1024 + 24)
(output / 'component-verification.json').write_text(json.dumps({'result': 'THP_SNAPSHOT_FORMAT_NONMUTATION_PASS',
    'buildSha256': sha(base_path), 'capture': str(capture), 'captureSha256': sha(capture),
    'probeSourceSha256': sha(source), 'readerSourceSha256': sha(public / 'stock_thp_frame_replay.cpp'),
    'verifierSha256': sha(Path(__file__).resolve()), 'executableSha256': sha(exe),
    'limits': ['Synthetic populated registers/NaN payload/signed zero/full3RAM banks, once-only and nonmutation.',
        'Not retail capture, complete native replay or Wii hardware/IRQ state equivalence.']}, indent=2) + '\n')
print('THP_SNAPSHOT_FORMAT_NONMUTATION_PASS', capture.stat().st_size)
