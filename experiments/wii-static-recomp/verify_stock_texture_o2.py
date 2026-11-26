"""Compare real GL texture pixels/cache behavior and binding-safe eviction with only the cache object optimized."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-texture-o2'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
parent_path = root / 'window-ios-o2-phases/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
assert (output / 'texture_cache_gl.cpp').read_bytes() == Path(build['originalSourcePath']).read_bytes()
assert sha(output / 'texture_cache_gl.cpp') == build['sourceSha256']
assert sha(output / 'texture_cache_gl.cpp.o') == build['objectSha256']
assert build['arguments'] == build['originalArguments'] + ['-O2']
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
archive = Path(build['archivePath'])
assert sha(archive) == build['archiveSha256']
old_archive = next(Path(arg) for arg in parent['linkCommand'] if Path(arg).name == 'libnwiiruntime.a')
for member, digest in build['members'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert hashlib.sha256(data).hexdigest() == digest
    if member != 'texture_cache_gl.cpp.o':
        assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
temporary = Path(tempfile.mkdtemp(prefix='openshsm-texture-o2-tests-', dir='/private/tmp'))
records = []
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
for probe_name, source, arguments, marker in [
    ('pixels', public / 'stock_texture_pixels_probe.cpp', [], 'NATIVE_TEXTURE_PIXEL_HIT_INVALIDATION_EFB_PASS'),
    ('eviction', public / 'stock_texture_eviction_probe.cpp', ['corrected'], 'BOUND_TEXTURE_EVICTION_PROTECTION_PASS1600')]:
    obj = temporary / f'{probe_name}.cpp.o'
    compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['originalArguments'],
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stderr[-2500:]
    endpoints = []
    for label, configuration in [('baseline', parent), ('candidate', build)]:
        command = list(configuration['linkCommand'])
        main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
        command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
        command.insert(1, str(obj))
        exe = temporary / f'{probe_name}-{label}'
        command[command.index('-o') + 1] = str(exe)
        linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
        assert linked.returncode == 0, linked.stderr[-2500:]
        endpoint = temporary / f'{label}-pixels.bin'
        args = [str(endpoint)] if probe_name == 'pixels' else arguments
        run = subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, timeout=60)
        log = output / f'{probe_name}-{label}.log'
        log.write_text(run.stdout + run.stderr)
        assert run.returncode == 0 and marker in run.stdout, run.stdout + run.stderr
        row = {'probe': probe_name, 'variant': label, 'sourceSha256': sha(source), 'objectSha256': sha(obj),
            'executablePath': str(exe), 'executableSha256': sha(exe), 'logSha256': sha(log)}
        if probe_name == 'pixels':
            row['endpointPath'] = str(endpoint)
            row['endpointSha256'] = sha(endpoint)
            row['cases'] = [list(map(int, values)) for values in re.findall(r'^PIXEL_CASE (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$', run.stdout, re.M)]
            assert len(row['cases']) == 172
            endpoints.append(endpoint)
        records.append(row)
    if probe_name == 'pixels':
        assert endpoints[0].read_bytes() == endpoints[1].read_bytes()
(output / 'component-verification.json').write_text(json.dumps({
    'result': 'TEXTURE_O2_REAL_GL_PIXELS172_EVICTION1600_EQUAL', 'buildSha256': sha(build_path),
    'verifierSha256': sha(Path(__file__)), 'records': records,
    'limits': ['Native hidden OpenGL,11supported cache formats/4sizes inclodd edge/3palette modes,172texel+palette-change cases exact RGBA bytes.',
        'Cache hits/texel and palette invalidation/currentunit/EFB registration survives clear and1600binding-safe admissions checked.',
        'Same corrected source/O2 only; matches existing native PC adapter, not independent original Wii GX hardware oracle.',
        'Per-case timing includes decode/GL upload/driver; single ordered runs not controlled CPU/FPS benchmark.',
        'Real game visual/audio/profile/lateLOOP behavior and candidate promotion still pending; test binaries/data private Mac temp.']}, indent=2) + '\n')
print('TEXTURE_O2_REAL_GL_PIXELS172_EVICTION1600_EQUAL')
