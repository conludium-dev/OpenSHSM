"""Actual DSP PCM and real SDL dummy driver/lifetime checks; no speaker/hardware acceptance."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-audio-callback'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
source, obj, exe = public / 'stock_audio_callback_probe.cpp', output / 'probe.cpp.o', output / 'callback-probe'
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
env['SDL_AUDIODRIVER'] = 'dummy'
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
log = output / 'probe.log'
log.write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'AUDIO_CALLBACK_DSP_PCM_BOUNDS_SDL_LIFETIME_PASS' in result.stdout, result.stderr
(output / 'component-verification.json').write_text(json.dumps({'result': 'AUDIO_CALLBACK_DSP_PCM_BOUNDS_SDL_LIFETIME_PASS',
    'buildSha256': sha(build_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'logSha256': sha(log), 'verifierSha256': sha(Path(__file__)),
    'limits': ['Actual MMIO/DSP/deadline signed PCM, partial/empty/unaligned stream/canaries/null/negative/odd length.',
        'Overreported/throwing/missing source refuses safely; >1024frames split without allocation.',
        'Real SDL dummy driver: paused open/no callback, audio progresses during200ms host stall, close joins/no after-close calls.',
        'Not real speakers/physical Wii/full game/GUI/human listening or all exception lifecycle acceptance.']}, indent=2) + '\n')
print(result.stdout.strip())
