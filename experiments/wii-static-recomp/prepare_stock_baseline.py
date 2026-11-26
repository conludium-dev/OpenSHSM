"""Prepare a complete source-only upstream runtime independently of the guarded laboratory."""
from pathlib import Path
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

project = Path('.').resolve()
cache = project / '_scratch/tmp/wii-static-recomp-tools'
output = project / 'work/private-game/static-recomp/stock-baseline'
source = output / 'upstream-source'
source.mkdir(parents=True, exist_ok=True)
tree = json.loads((cache / 'nwii-tree.json').read_text())
revision = '595f176f1d24cc54ff2e8389feed12d7fb553cc2'
assert tree['sha'] == revision and not tree.get('truncated')


def fetch(row):
    name = row['path']
    selected = name in ('README.md', 'LICENSE', 'CMakeLists.txt') or (
        name.startswith(('nWiiAnalyzer/', 'nWiiRecomp/', 'nWiiRuntime/')) and
        name.endswith(('.h', '.hpp', '.c', '.cpp', '.mm', '.in', 'CMakeLists.txt')))
    if row['type'] != 'blob' or not selected:
        return None
    path = source / name
    cached = cache / 'NWiiRecomp' / name
    data = path.read_bytes() if path.exists() else cached.read_bytes() if cached.exists() else b''
    digest = lambda value: hashlib.sha1(b'blob ' + str(len(value)).encode() + b'\0' + value).hexdigest()
    downloaded = False
    if digest(data) != row['sha']:
        data = subprocess.run(['curl', '-fLsS', '--max-time', '60',
            'https://raw.githubusercontent.com/BlackLineInteractive/NWiiRecomp/' + revision + '/' + name],
            capture_output=True, check=True).stdout
        downloaded = True
    assert len(data) == row['size'] and digest(data) == row['sha'], name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)
    return name, {'sha256': hashlib.sha256(data).hexdigest(), 'gitBlob': row['sha'], 'downloaded': downloaded}


with ThreadPoolExecutor(max_workers=4) as pool:
    files = dict(row for row in pool.map(fetch, tree['tree']) if row is not None)
dependencies = {}
for name, repository, tag in (('tomlplusplus', 'marzer/tomlplusplus', 'v3.4.0'),
        ('sdl2', 'libsdl-org/SDL', 'release-2.28.5'), ('glad', 'Dav1dde/glad', 'v0.1.36')):
    archive = output / 'dependencies' / (name + '.tar.gz')
    archive.parent.mkdir(exist_ok=True)
    url = 'https://codeload.github.com/' + repository + '/tar.gz/refs/tags/' + tag
    if not archive.exists():
        result = subprocess.run(['curl', '-fLsS', '--max-time', '120', url], capture_output=True, check=True)
        archive.write_bytes(result.stdout)
    dependencies[name] = {'url': url, 'path': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
game = project / 'work/private-game/disc/DATA'
assert hashlib.sha256((game / 'sys/main.dol').read_bytes()).hexdigest() == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
config = output / 'recompile.toml'
config.write_text('project_name = "OpenSHSMStockBaseline"\ninput_game_dir = ' + json.dumps(str(game)) +
    '\noutput_dir = ' + json.dumps(str(output / 'export')) + '\nruntime_source_dir = ' +
    json.dumps(str(source / 'nWiiRuntime')) + '\nsplit_output = true\ninstructions_per_file = 20000\n')
(output / 'preparation.json').write_text(json.dumps({'result': 'STOCK_SOURCE_AND_INPUTS_PREPARED',
    'repository': 'https://github.com/BlackLineInteractive/NWiiRecomp', 'revision': revision, 'files': files,
    'dependencies': dependencies, 'configSha256': hashlib.sha256(config.read_bytes()).hexdigest(),
    'recipeSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'limits': ['Unmodified upstream compiler/runtime source. Orchestrator omits optional Studio and SDK signature scan.',
        'No guest assets downloaded; original game and guarded pipeline untouched. Build and execution still pending.']}, indent=2) + '\n')
print('Prepared complete stock compiler/runtime source:', len(files), 'files; copied independent source snapshot, no game download')
