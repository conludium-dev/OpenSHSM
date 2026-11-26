"""Replay the same captured finite IDCT inputs with strict output-byte comparison."""
from pathlib import Path
import hashlib
import json
import os
import re
import statistics
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'headless-constant-fp/idct-benchmark'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
old = root / 'observer-env-research/idct-benchmark'
old_report = json.loads((old / 'comparison.json').read_text())
source, obj = old / 'benchmark.cpp', old / 'benchmark.cpp.o'
assert sha(source) == old_report['benchmarkSourceSha256']
assert sha(obj) == old_report['benchmarkObjectSha256']
assert old_report['result'] == 'CAPTURED_IDCT_ENV_CACHE_IDENTICAL_500_REPLAYS'
guard_path = root / 'headless-constant-fp/guard-verification.json'
assert json.loads(guard_path.read_text())['result'] == 'CONSTANT_FP_DIFFERENTIAL_PASS'
executables = {}
for name, directory in [('baseline', 'headless-movie-timing'), ('specialized', 'headless-constant-fp')]:
    base_path = root / directory / 'build.json'
    base = json.loads(base_path.read_text())
    for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
        assert sha(Path(path)) == expected
    command = list(base['linkCommand'])
    archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
    assert sha(archive) == base['archiveSha256']
    command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    command.insert(1, str(obj))
    exe = output / (name + '-benchmark')
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
    executables[name] = {'path': str(exe), 'sha256': sha(exe), 'baseBuildSha256': sha(base_path)}
fixtures = sorted(root.glob('window-idct-fixtures-blocks120-thp-block*.txt'))
assert len(fixtures) == 3
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
dol = Path('work/private-game/disc/DATA/sys/main.dol').resolve()
assert sha(dol) == old_report['dolSha256']
rows = []
for fixture in fixtures:
    evidence = next(row for row in old_report['fixtures'] if row['fixture'] == fixture.name)
    assert sha(fixture) == evidence['fixtureSha256']
    values, outputs = [], []
    for iteration in range(3):
        for name in (('baseline', 'specialized') if iteration % 2 == 0 else ('specialized', 'baseline')):
            raw = output / (fixture.stem + f'-{name}-{iteration}.bin')
            result = subprocess.run([executables[name]['path'], str(dol), str(fixture), str(raw)],
                env=env, capture_output=True, text=True, timeout=60)
            log = output / (fixture.stem + f'-{name}-{iteration}.log')
            log.write_text(result.stdout + result.stderr)
            assert result.returncode == 0, (name, fixture.name, result.returncode, result.stdout, result.stderr)
            match = re.search(r'IDCT_BENCHMARK iterations=500 ns=(\d+) digest=([0-9a-f]+)', result.stdout)
            assert match
            outputs.append(raw.read_bytes())
            values.append({'variant': name, 'nanoseconds': int(match[1]), 'outputSha256': sha(raw), 'logSha256': sha(log)})
    assert all(value == outputs[0] for value in outputs)
    assert sha(output / (fixture.stem + '-baseline-0.bin')) == evidence['results'][0]['outputSha256']
    medians = {name: statistics.median(row['nanoseconds'] / 500 for row in values if row['variant'] == name) for name in executables}
    rows.append({'fixture': fixture.name, 'fixtureSha256': sha(fixture), 'results': values,
        'medianNs': medians, 'ratio': medians['baseline'] / medians['specialized']})
(output / 'comparison.json').write_text(json.dumps({'result': 'CONSTANT_FP_CAPTURED_IDCT_BYTE_IDENTICAL_9000',
    'executables': executables, 'fixtures': rows, 'guardVerificationSha256': sha(guard_path),
    'benchmarkSourceSha256': sha(source), 'benchmarkObjectSha256': sha(obj), 'oldComparisonSha256': sha(old / 'comparison.json'),
    'verifierSha256': sha(Path(__file__).resolve()), 'dolSha256': sha(dol),
    'limits': ['3native-captured finite inputs,500replays x3alternating passes x2variants; fullbackedRAM restored outside timer.',
        '7captured ranges18644bytes match within/acrosspasses and earlier report; not full original memory oracle.',
        'Fixture FP-active/HID2 enabled/EEdisabled, not live lazy-FPU/interrupt or whole movie/rendered FPS acceptance.']}, indent=2) + '\n')
print('CONSTANT_FP_CAPTURED_IDCT_BYTE_IDENTICAL_9000')
print(json.dumps([{key: row[key] for key in ('fixture', 'medianNs', 'ratio')} for row in rows], indent=2))
