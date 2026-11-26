"""Fetch source-only tool snapshots; never fetch guest executables or game assets."""
from pathlib import Path
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

root = Path('_scratch/tmp/wii-static-recomp-tools')
root.mkdir(parents=True, exist_ok=True)
expected_revision = '595f176f1d24cc54ff2e8389feed12d7fb553cc2'
tree_path = root / 'nwii-tree.json'
if not tree_path.exists():
    subprocess.run(['curl', '-fLsS', 'https://api.github.com/repos/BlackLineInteractive/NWiiRecomp/git/trees/' +
                    expected_revision + '?recursive=1', '-o', str(tree_path)], check=True)
tree = json.loads((root / 'nwii-tree.json').read_text())
revision = tree['sha']
assert revision == expected_revision and not tree.get('truncated'), 'Unexpected upstream snapshot'
destination = root / 'NWiiRecomp'
def fetch(row):
    name = row['path']
    selected = (name in ('README.md', 'LICENSE', '.gitignore', 'CMakeLists.txt', 'SHOWCASE.md') or
                name.startswith(('nWiiAnalyzer/', 'nWiiRecomp/', 'nWiiRuntime/')) and
                name.endswith(('.h', '.cpp', '.java', '.md', 'CMakeLists.txt')))
    if row['type'] != 'blob' or not selected:
        return None
    path = destination / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        data = path.read_bytes()
        digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if digest == row['sha']:
            return name, hashlib.sha256(data).hexdigest()
    data = subprocess.run(['curl', '-fLsS', '--max-time', '60',
                           'https://raw.githubusercontent.com/BlackLineInteractive/NWiiRecomp/' + revision + '/' + name],
                          capture_output=True, check=True).stdout
    assert len(data) == row['size'], name
    assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == row['sha'], name
    path.write_bytes(data)
    return name, hashlib.sha256(data).hexdigest()

with ThreadPoolExecutor(max_workers=4) as pool:
    manifest = dict(row for row in pool.map(fetch, tree['tree']) if row is not None)
report = {'repository': 'https://github.com/BlackLineInteractive/NWiiRecomp', 'revision': revision,
          'files': manifest, 'excluded': ['images', 'Studio media/fonts', 'dolphin signature data', 'guest binaries/assets']}
(root / 'nwii-source-manifest.json').write_text(json.dumps(report, indent=2) + '\n')
print('Fetched', len(manifest), 'source-only NWiiRecomp files at', revision)
