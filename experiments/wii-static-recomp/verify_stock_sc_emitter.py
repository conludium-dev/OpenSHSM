"""Compile the actual patched emitter and compare all analyzed DOL SC functions."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
from stock_sc_pc_patch import adapt, adapt_emitter

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'sc-emitter-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
source = root / 'upstream-source/nWiiRecomp/src/recompiler.cpp'
original_hash = sha(source)
patched = output / 'recompiler.cpp'
patched.write_text(adapt_emitter(source.read_text()))
flags = (root / 'tool-build/nWiiRecomp/CMakeFiles/nwiirecomp_lib.dir/flags.make').read_text()
arguments = []
for key in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments.extend(shlex.split(re.search(r'^' + key + r' = (.*)$', flags, re.M)[1]))
compiler = '/Library/Developer/CommandLineTools/usr/bin/c++'
def run(command, log, cwd=None):
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd, timeout=180)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    return result.stdout

obj = output / 'recompiler.cpp.o'
probe_obj = output / 'probe.cpp.o'
run([compiler, *arguments, '-c', str(patched), '-o', str(obj)], output / 'compile.log')
run([compiler, *arguments, '-c', str(public / 'stock_sc_emitter_probe.cpp'), '-o', str(probe_obj)], output / 'probe-compile.log')
link_dir = root / 'tool-build/nWiiRecomp'
command = shlex.split((link_dir / 'CMakeFiles/nwiirecomp.dir/link.txt').read_text())
command[command.index('CMakeFiles/nwiirecomp.dir/src/main.cpp.o')] = str(probe_obj)
dol_path = Path('work/private-game/disc/DATA/sys/main.dol').resolve()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
records = {}
for name in ('baseline', 'corrected'):
    cmd = list(command)
    if name == 'corrected':
        cmd[cmd.index('libnwiirecomp_lib.a')] = str(obj)
        cmd.insert(1, str(link_dir / 'CMakeFiles/nwiirecomp_lib.dir/src/symbols.cpp.o'))
    exe = output / (name + '-probe')
    cmd[cmd.index('-o') + 1] = str(exe)
    run(cmd, output / (name + '-link.log'), link_dir)
    stdout = run([str(exe), str(dol_path), str(output / name)], output / (name + '.log'))
    records[name] = {'executableSha256': sha(exe), 'stdout': stdout}
baseline_files = sorted((output / 'baseline').glob('*.cpp'))
assert {p.name for p in baseline_files} == {p.name for p in (output / 'corrected').glob('*.cpp')}
comparisons = []
for baseline in baseline_files:
    corrected = output / 'corrected' / baseline.name
    expected, sites = adapt(baseline.read_text(), dol_path.read_bytes())
    assert expected == corrected.read_text(), baseline.name
    comparisons.append({'function': hex(int(baseline.stem)), 'sites': [hex(site) for site in sites],
        'baselineSha256': sha(baseline), 'correctedSha256': sha(corrected)})
assert comparisons and sha(source) == original_hash
dependencies = [Path(__file__).resolve(), public / 'stock_sc_pc_patch.py', public / 'stock_sc_emitter_probe.cpp']
(output / 'comparison.json').write_text(json.dumps({'result': 'COMPILED_SC_EMITTER_ALL_ANALYZED_SITES_PASS',
    'dolSha256': sha(dol_path), 'originalEmitterSha256': original_hash, 'patchedEmitterSha256': sha(patched),
    'patchedObjectSha256': sha(obj), 'records': records, 'functions': comparisons,
    'dependencies': {str(path): sha(path) for path in dependencies},
    'limits': ['Actual analyzer and baseline/corrected compiled emitter; all discovered SC functions compared byte-for-byte except verified PC synchronization.',
        'Analyzer coverage does not prove every executable instruction was discovered.',
        'Generated bodies are not yet compiled/linked into the full runtime; no live movie/GPU/hardware acceptance.']}, indent=2) + '\n')
print('COMPILED_SC_EMITTER_ALL_ANALYZED_SITES_PASS', len(comparisons), sum(len(row['sites']) for row in comparisons))
