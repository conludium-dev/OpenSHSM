"""Reproduce cache eviction deleting already-selected textures on native GL."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
parser = argparse.ArgumentParser()
parser.add_argument('--corrected', action='store_true')
args = parser.parse_args()
output = root / ('headless-texture-eviction' if args.corrected else 'texture-eviction-research')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / ('headless-texture-eviction' if args.corrected else 'headless-texture-units') / 'build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
parent = json.loads((root / 'headless-tev-banks/build.json').read_text())
record = next(row for row in parent['compiled'] if row['member'] == 'texture_cache_gl.cpp.o')
source, obj = public / 'stock_texture_eviction_probe.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
command = list(base['linkCommand'])
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'eviction-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
result = subprocess.run([str(exe), *(['corrected'] if args.corrected else [])], capture_output=True, text=True, timeout=30)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
marker = 'BOUND_TEXTURE_EVICTION_PROTECTION_PASS1600' if args.corrected else 'BOUND_TEXTURE_EVICTION_LOSS_REPRODUCED'
assert marker in result.stdout
(output / 'component-verification.json').write_text(json.dumps({'result': marker,
    'buildSha256': sha(base_path), 'sourceSha256': sha(source), 'executableSha256': sha(exe),
    'logSha256': sha(output / 'probe.log'), 'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Actual linked cache/native hiddenGL,512prefill and selected3slots; fixed test1600total admissions.',
        'Synthetic texture bindings, not actual Wii draw/wholegame flicker/FPS acceptance.']}, indent=2) + '\n')
print(result.stdout.strip())
