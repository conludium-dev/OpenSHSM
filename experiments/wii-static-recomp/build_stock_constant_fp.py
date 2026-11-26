"""Recompile only retained decoder unit37 with constant-word guard specialization."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_constant_fp_patch import specialize

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-constant-fp'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-movie-timing/build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected, path
command = list(base['linkCommand'])
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == base['archiveSha256']
old = next(Path(arg) for arg in command if Path(arg).name == 'output_37.cpp.o')
original = old.with_suffix('')
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
header = public / 'stock_fp_unavailable.h'
generated, text, sites = specialize(header.read_text(), original.read_text(), dol_path.read_bytes())
(output / 'constant_fp_guard.h').write_text(generated)
source, obj = output / original.name, output / old.name
source.write_text(text)
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-I', str(original.parent), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command[command.index(str(old))] = str(obj)
exe = output / 'OpenSHSMStockConstantFP'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'CONSTANT_FP_BUILT_BEHAVIOR_PERFORMANCE_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'dolSha256': sha(dol_path), 'originalSourceSha256': sha(original),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'executableSha256': sha(exe),
    'archiveSha256': sha(archive), 'linkCommand': command, 'sites': sites,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_constant_fp_patch.py',
        header, output / 'constant_fp_guard.h', public / 'stock_movie_timing.h']},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['Only unit37 guard classification specialized; all runtime MSR/HID2 checks and trap order retained.',
        '74other guests and full runtime archive unchanged; no original instructions/FP arithmetic changed.',
        'Native differential/replay/live validation still required, not independently original Wii behavior proof.']}, indent=2) + '\n')
print('CONSTANT_FP_BUILT_BEHAVIOR_PERFORMANCE_UNVERIFIED', len(sites))
