"""Validate one-header guest-unit delta and actual cache-range endpoints against parent."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
args = parser.parse_args()
path = args.build.resolve()
build = json.loads(path.read_text())
root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent_path = root / 'window-post-present/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
for file, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(file) == digest
source_text = Path(build['originalSourcePath']).read_text()
for before, after in build['sourcePatches']:
    assert source_text.count(before) == 1 and after == ''
    source_text = source_text.replace(before, after, 1)
assert source_text == Path(build['sourcePath']).read_text()
assert sha(build['sourcePath']) == build['sourceSha256']
assert sha(build['observerHeaderPath']) == build['observerHeaderSha256']
assert 'if (!prefix || stage > 3)' in Path(build['observerHeaderPath']).read_text()
assert sha(build['objectPath']) == build['objectSha256']
assert sha(build['executablePath']) == build['executableSha256']
expected = list(parent['linkCommand'])
expected[expected.index(build['originalObjectPath'])] = build['objectPath']
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
cache = Path(tempfile.mkdtemp(prefix='openshsm-context-stage-tests-', dir='/private/tmp'))
probe = public / 'stock_cache_range_stage_probe.cpp'
obj = cache / 'probe.cpp.o'
flags_path = root / 'window-movie-late/build.json'
flags = json.loads(flags_path.read_text())['changes']['37']['arguments']
run = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags, '-UNDEBUG',
    '-c', str(probe), '-o', str(obj)], capture_output=True, text=True, timeout=60)
assert run.returncode == 0, run.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
records = []
reference = None
for label, configuration in [('baseline', parent), ('candidate', build)]:
    link = list(configuration['linkCommand'])
    main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
    link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    link.insert(1, str(obj))
    exe = cache / label
    link[link.index('-o') + 1] = str(exe)
    run = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-3000:]
    for setting in ('disabled', 'enabled'):
        selected_env = dict(env)
        prefix = cache / f'{label}-{setting}-observer'
        if setting == 'enabled':
            selected_env['NWII_THPDUMP'] = str(prefix)
        raw = cache / f'{label}-{setting}.bin'
        run = subprocess.run([str(exe), str(raw)], env=selected_env, capture_output=True, text=True, timeout=30)
        assert run.returncode == 0 and 'PPC_ENDPOINT_PASS234' in run.stdout, run.stdout + run.stderr
        assert not list(cache.glob(prefix.name + '*'))
        endpoint = raw.read_bytes()
        if reference is None:
            reference = endpoint
        assert endpoint == reference
        records.append({'variant': label, 'setting': setting, 'endpointPath': str(raw), 'endpointSha256': sha(raw),
            'executablePath': str(exe), 'executableSha256': sha(exe), 'stdout': run.stdout})
report = {'result': 'CONTEXT_STAGE_GATE_CACHE234_ENABLED_DISABLED_PARENT_ENDPOINTS_EQUAL',
    'buildSha256': sha(path), 'dependencies': {str(file): sha(file) for file in [Path(__file__).resolve(),
        probe, flags_path, parent_path]}, 'records': records,
    'limits': ['Actual linked cache-range entry224 and resume10 cases, independently checked normal-entry PPC GPR/CTR/CR/instruction formulas.',
        'Enabled/disabled observer modes all endpoints equal and rejected stages create no records.',
        'No active original IRQ/device producer; callback/SDK/SC/DEC/live/performance gates still pending.',
        'Same native original-operation reconstruction, not physical Wii cache/timing oracle.']}
proof_path = cache / 'verification.json'
proof_path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], proof_path)
