"""Compare actual original/observed DSP PCM, zero-fill, deadline, late coalescing and stop."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-dsp-supply'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
parent = json.loads((root / 'window-debug-overlay/build.json').read_text())
source, obj = public / 'stock_dsp_supply_probe.cpp', output / 'probe.cpp.o'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *parent['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
assert compiled.returncode == 0, compiled.stderr[-3000:]
rows = []
for label, command in [('baseline', list(parent['linkCommand'])), ('observed', list(build['linkCommand']))]:
    main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
    command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    command.insert(1, str(obj))
    exe = output / f'{label}-probe'
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
    env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
    if label == 'observed':
        env['NWII_DSP_SUPPLY'] = '1'
    result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
    log = output / f'{label}-probe.log'
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'DSP_SUPPLY_PCM_SCHEDULE_NONMUTATION_PASS' in result.stdout, (result.returncode, result.stdout, result.stderr)
    rows.append({'variant': label, 'executableSha256': sha(exe), 'logSha256': sha(log)})
(output / 'component-verification.json').write_text(json.dumps({
    'result': 'DSP_SUPPLY_PCM_SCHEDULE_NONMUTATION_PASS', 'buildSha256': sha(build_path),
    'sourceSha256': sha(source), 'verifierSha256': sha(Path(__file__).resolve()), 'rows': rows,
    'limits': ['Actual DSP/MMIO/EventScheduler in both full archives, same384-byte PCM payload/zero-fill/RAM retained.',
        'Synthetic manual TB deadline/late coalescing/stop, not original Wii timing/physical output/movie test.']}, indent=2) + '\n')
print('DSP_SUPPLY_PCM_SCHEDULE_NONMUTATION_PASS')
