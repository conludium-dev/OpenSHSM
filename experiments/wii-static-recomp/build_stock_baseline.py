"""Run explicit stock build phases, retaining logs and exact upstream source hashes."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=('configure', 'toolchain', 'export', 'game-configure', 'game-build'))
args = parser.parse_args()
project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
prep = json.loads((root / 'preparation.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for name, record in prep['files'].items():
    assert sha(root / 'upstream-source' / name) == record['sha256'], name
cmake = project / '_scratch/tmp/openshsm-stock-build-tools/cmake/data/bin/cmake'
assert cmake.exists()
orchestrator = root / 'orchestrator'
orchestrator.mkdir(exist_ok=True)
(orchestrator / 'CMakeLists.txt').write_bytes((project / 'experiments/wii-static-recomp/stock-baseline.cmake.txt').read_bytes())
dependency_args = []
for name in ('tomlplusplus', 'sdl2', 'glad'):
    dependency_args.append('-DFETCHCONTENT_SOURCE_DIR_' + name.upper() + '=' + str(root / 'tool-build/_deps' / (name + '-src')))
commands = {
    'configure': [str(cmake), '-S', str(orchestrator), '-B', str(root / 'tool-build'), '-DNWII_STOCK_ROOT=' + str(root), '-DCMAKE_BUILD_TYPE=Debug'],
    'toolchain': [str(cmake), '--build', str(root / 'tool-build'), '--target', 'nwiirecomp', '--parallel', '4'],
    'export': [str(root / 'tool-build/nWiiRecomp/nwiirecomp'), str(root / 'recompile.toml')],
    'game-configure': [str(cmake), '-S', str(root / 'export'), '-B', str(root / 'export/build'), '-DCMAKE_BUILD_TYPE=Debug', '-DGLAD_REPRODUCIBLE=ON', *dependency_args],
    'game-build': [str(cmake), '--build', str(root / 'export/build'), '--parallel', '4']
}
log = root / (args.phase + '.log')
with log.open('w') as stream:
    result = subprocess.run(commands[args.phase], cwd=root, stdout=stream, stderr=subprocess.STDOUT, timeout=900)
report = {'phase': args.phase, 'returncode': result.returncode, 'command': commands[args.phase],
    'recipeSha256': sha(Path(__file__)), 'preparationSha256': sha(root / 'preparation.json'),
    'orchestratorSha256': sha(orchestrator / 'CMakeLists.txt'), 'logSha256': sha(log),
    'limits': ['Unmodified upstream runtime/compiler files; no game binary or asset download.',
        'Build success is not game execution or visual verification.']}
(root / (args.phase + '-result.json')).write_text(json.dumps(report, indent=2) + '\n')
print(args.phase, 'terminal:', result.returncode, 'log:', log)
if result.returncode:
    print('\n'.join(log.read_text(errors='replace').splitlines()[-30:]))
raise SystemExit(result.returncode)
