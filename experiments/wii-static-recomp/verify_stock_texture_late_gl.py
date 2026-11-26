"""Compare actual OpenGL texture outputs with disabled, enabled and refused diagnostic settings."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path(__file__).resolve().parent
output = root / 'window-texture-late'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
parent_path = root / 'window-dispatch-select/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
assert sha(Path(build['archivePath'])) == build['archiveSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-texture-late-tests-', dir='/private/tmp'))
base_env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
records = []
for name, source, marker in [('pixels', public / 'stock_texture_pixels_probe.cpp', 'NATIVE_TEXTURE_PIXEL_HIT_INVALIDATION_EFB_PASS'),
    ('eviction', public / 'stock_texture_eviction_probe.cpp', 'BOUND_TEXTURE_EVICTION_PROTECTION_PASS1600')]:
    obj = cache / f'{name}.cpp.o'
    compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'],
        '-UNDEBUG', '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stderr[-3000:]
    endpoints = []
    for label in ('baseline', 'disabled', 'enabled', 'invalid'):
        configuration = parent if label == 'baseline' else build
        link = list(configuration['linkCommand'])
        main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
        link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
        link.insert(1, str(obj))
        exe = cache / f'{name}-{label}'
        link[link.index('-o') + 1] = str(exe)
        linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
        assert linked.returncode == 0, linked.stderr[-3000:]
        directory = cache / f'{name}-{label}-textures'
        directory.mkdir()
        env = dict(base_env)
        if label in ('enabled', 'invalid'):
            env.update(NWII_TEXTURE_OBSERVE=str(directory), NWII_TEXTURE_COHERENCE='1',
                NWII_TEXTURE_CAPTURE_AFTER_MS='0' if label == 'enabled' else 'invalid')
        endpoint = cache / f'{name}-{label}.bin'
        args = [str(endpoint)] if name == 'pixels' else ['corrected']
        run = subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, timeout=60)
        assert run.returncode == 0 and marker in run.stdout, run.stdout + run.stderr
        if name == 'pixels':
            assert len(re.findall(r'^PIXEL_CASE ', run.stdout, re.M)) == 172
            endpoints.append(endpoint.read_bytes())
        files = list(directory.iterdir())
        if label == 'enabled':
            raw = list(directory.glob('texture-*.raw'))
            assert raw and len(list(directory.glob('*.txt'))) <= 256
            assert sum(path.stat().st_size for path in files if path.suffix in ('.raw', '.rgba', '.tlut')) <= 96 * 1024 * 1024
            for coherence in directory.glob('*.coherence.txt'):
                values = list(map(int, coherence.read_text().split()))
                assert len(values) == 8 and values[1] >= values[0] and values[4] == 1
                assert values[2] == values[3] and values[5] == 0
        else:
            assert not files
        records.append({'probe': name, 'setting': label, 'executablePath': str(exe), 'executableSha256': sha(exe),
            'stdout': run.stdout, 'captureDirectory': str(directory), 'files': len(files)})
    if name == 'pixels':
        assert all(endpoint == endpoints[0] for endpoint in endpoints)
(output / 'gl-verification.json').write_text(json.dumps({
    'result': 'LATE_TEXTURE_DISABLED_ENABLED_INVALID_GL_PIXELS172_EVICTION1600_EQUAL',
    'buildSha256': sha(build_path), 'verifierSha256': sha(Path(__file__)), 'records': records,
    'limits': ['Actual hidden GL cache pixels/binding/eviction unchanged in baseline/disabled/enabled/invalid cases.',
        'Enabled copy pairs equal in deterministic texture fixtures; not concurrent original producer/race proof.',
        '128records/perkey/aggregate caps inspected, not exhaustive filesystem failure or hostile input proof.',
        'Native CPU callback/frame/timer and live late game acceptance remain pending; no promotion.']}, indent=2) + '\n')
print('LATE_TEXTURE_DISABLED_ENABLED_INVALID_GL_PIXELS172_EVICTION1600_EQUAL')
