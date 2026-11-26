"""Actual DSP/MMIO/deadlines and existing refill with modeled fixed-rate device, not a hardware claim."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'audio-cadence-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = root / 'window-audio-refill/build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
source, obj, exe = public / 'stock_audio_cadence_probe.cpp', output / 'probe.cpp.o', output / 'cadence-probe'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
assert result.returncode == 0, result.stderr[-3000:]
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env['NWII_DSP_SUPPLY'] = '1'
rows = []
for frequency in (40500000, 60750000):
    for mode in ('steady', 'slow', 'stall'):
        result = subprocess.run([str(exe), mode, str(frequency)], env=env, capture_output=True, text=True, timeout=30)
        log = output / f'{mode}-{frequency}.log'
        log.write_text(result.stdout + result.stderr)
        assert result.returncode == 0 and 'AUDIO_CADENCE_PASS' in result.stdout, result.stderr[-3000:]
        rows.append({'mode': mode, 'frequency': frequency, 'stdout': result.stdout, 'logSha256': sha(log)})
(output / 'verification.json').write_text(json.dumps({'result': 'ACTUAL_DSP_REFILL_CADENCE6_PASS',
    'buildSha256': sha(build_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'headerSha256': sha(public / 'stock_audio_refill.h'),
    'verifierSha256': sha(Path(__file__)), 'rows': rows,
    'limits': ['Actual private runtime/MMIO/deadlines/PCM/refill; device consumption deterministically modeled, not SDL hardware.',
        'Existing64ms queue:16ms cadence no lost/missing;96ms consumer gap misses1024frames/gap despite available PCM.',
        '1200ms stall overflows existing32000frame ring by6400frames; no buffer enlargement or timing change.',
        '32k ramp only; not48k/whole-game/physical-Wii/live root-cause acceptance.']}, indent=2) + '\n')
print('ACTUAL_DSP_REFILL_CADENCE6_PASS')
for row in rows:
    print(row['frequency'], row['stdout'].splitlines()[-1])
