"""Verify candidate archive/source delta and actual parse-versus-execute acknowledgement."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path(__file__).resolve().parent
output = root / 'window-pe-execute'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
parent_path = root / 'window-texture-late/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
assert sha(Path(build['archivePath'])) == build['archiveSha256']
for name, row in build['changes'].items():
    original = Path(row['originalPath']).read_text()
    expected = original
    for before, after in row['patches']:
        assert expected.count(before) == 1
        expected = expected.replace(before, after, 1)
    assert row['include'] + expected == Path(row['sourcePath']).read_text()
    assert sha(Path(row['objectPath'])) == row['objectSha256']
    member = subprocess.check_output(['/usr/bin/ar', '-p', build['archivePath'], name + '.o'])
    assert hashlib.sha256(member).hexdigest() == row['objectSha256']
for member, digest in build['members'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', build['archivePath'], member])
    assert hashlib.sha256(data).hexdigest() == digest
    if member not in {name + '.o' for name in build['changes']}:
        assert data == subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], member])
expected = list(parent['linkCommand'])
expected[expected.index(parent['archivePath'])] = build['archivePath']
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
cache = Path(tempfile.mkdtemp(prefix='openshsm-pe-execute-tests-', dir='/private/tmp'))
probe = public / 'stock_pe_execute_probe.cpp'
obj = cache / 'probe.cpp.o'
flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']['37']['arguments']
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags, '-UNDEBUG',
    '-c', str(probe), '-o', str(obj)], capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
link = list(build['linkCommand'])
main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
link.insert(1, str(obj))
exe = cache / 'pe-execute-probe'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
assert run.returncode == 0 and 'PE_PARSE_NO_ACK_APPLY_ACK5_COMPLETION_PREFIX_BOUNDS7_PASS' in run.stdout, run.stdout + run.stderr
(output / 'execution-verification.json').write_text(json.dumps({
    'result': 'PE_PARSE_NO_ACK_ORDERED_APPLY5_PREFIX_BOUNDS7_VERIFIED', 'buildSha256': sha(build_path),
    'probeSha256': sha(probe), 'verifierSha256': sha(Path(__file__)), 'stdout': run.stdout,
    'executablePath': str(exe), 'executableSha256': sha(exe), 'linkCommand': link,
    'limits': ['Actual parser no longer signals PE; explicit Apply does so in five native cases, negative/truncated cases retained.',
        'Pure bounds helper selects completed copy/finish/token prefix and preserves copy-derived stale-draw boundary.',
        'Actual ProcessGXFifo/Renderer/glFinish/preceding-texture execution ordering not yet exercised by this probe.',
        'Full GL/CPU/frame/timer/live coherence and performance gates pending; no promotion.']}, indent=2) + '\n')
print('PE_PARSE_NO_ACK_ORDERED_APPLY5_PREFIX_BOUNDS7_VERIFIED')
