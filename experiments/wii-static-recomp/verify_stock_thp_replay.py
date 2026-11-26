"""Replay one actual decoder entry with explicit FP-active/EE-disabled fixture policy."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-thp-snapshot/replay'
output.mkdir(exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument('--tag', default='decoder-snapshot')
args = parser.parse_args()
assert args.tag.replace('-', '').isalnum()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
source, obj = public / 'stock_thp_frame_replay.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
snapshot = root / f'headless-sc-pc-{args.tag}-decoder-entry.bin'
prefix = root / f'headless-sc-pc-{args.tag}-thp'
expected = b''.join(Path(str(prefix) + f'-frame0-{plane}.bin').read_bytes() for plane in ('Y', 'U', 'V'))
assert len(expected) == 460800
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
rows = []
for name in ('headless-movie-timing', 'headless-constant-fp'):
    build_path = root / name / 'build.json'
    base = json.loads(build_path.read_text())
    for path, value in {**base['dependencies'], **base['retainedLinkInputs']}.items():
        assert sha(Path(path)) == value
    command = list(base['linkCommand'])
    command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    command.insert(1, str(obj))
    exe = output / (name + '-replay')
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
    raw = output / (name + '.yuv')
    result = subprocess.run([str(exe), str(snapshot), str(raw)], env=env, capture_output=True, text=True, timeout=30)
    log = output / (name + '.log')
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (name, result.returncode, result.stdout, result.stderr)
    assert raw.read_bytes() == expected, 'Replay differs from actual complete live frame'
    rows.append({'variant': name, 'buildSha256': sha(build_path), 'executableSha256': sha(exe),
        'outputSha256': sha(raw), 'logSha256': sha(log), 'stdout': result.stdout.strip()})
(output / 'verification.json').write_text(json.dumps({'result': 'COMPLETE_FRAME_REPLAY_LIVE_BYTES_IDENTICAL2',
    'snapshotSha256': sha(snapshot), 'comparedBytesEach': len(expected), 'variants': rows,
    'probeSourceSha256': sha(source), 'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Same complete native decoder entry/backed RAM in both variants; FP-active/EE-disabled fixture.',
        'Host devices/queues/instructionImages not snapshotted; not original Wii save-state or IRQ equivalence.',
        'One captured pale frame; colored frame and statistically controlled timing profile still pending.']}, indent=2) + '\n')
print('COMPLETE_FRAME_REPLAY_LIVE_BYTES_IDENTICAL2')
print(json.dumps(rows, indent=2))
