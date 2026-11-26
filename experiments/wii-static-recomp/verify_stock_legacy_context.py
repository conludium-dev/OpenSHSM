"""Audit the minimal legacy policy and replay the retained observed-shape nested fixture before/after."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_legacy_context_patch import adapt

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-cache-filtered', root / 'window-legacy-context'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
assert (output / 'ios.cpp').read_text() == adapt((base / 'ios.cpp').read_text())
for name, key in [('ios.cpp', 'sourceSha256'), ('ios.cpp.o', 'objectSha256'),
    ('libnwiiruntime.a', 'archiveSha256'), ('OpenSHSMStockLegacyContext', 'executableSha256')]:
    assert sha(output / name) == build[key]
assert sha(base / 'stock_context_observation.h') == build['contextHeaderSha256']
assert sha(Path('experiments/wii-static-recomp/stock_legacy_context_patch.py')) == build['adapterSha256']
assert sha(Path('experiments/wii-static-recomp/build_stock_legacy_context.py')) == build['recipeSha256']
for path, expected in build['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
for member, expected in build['retainedRuntimeMembers'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(output / 'libnwiiruntime.a'), member])
    assert hashlib.sha256(data).hexdigest() == expected
original_path = root / 'sdk-irq-tail/original-comparison.json'
original = json.loads(original_path.read_text())
assert original['result'] == 'ORIGINAL_NATIVE_SDK_IRQ_TAIL_COMPARISON_PASS' and len(original['cases']) == 12
fixture_report_path = root / 'nested-context-fixture/comparison.json'
fixture_report = json.loads(fixture_report_path.read_text())
fixture = root / 'nested-context-fixture/observed-selection.bin'
assert sha(fixture) == fixture_report['fixtureSha256']
source = Path('experiments/wii-static-recomp/stock_nested_context_probe.cpp').resolve()
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'main_output.cpp')
obj = output / 'observed-probe.cpp.o'
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(source), '-o', str(obj)],
    capture_output=True, check=True, timeout=60)
results = {}
for variant in ('baseline', 'corrected'):
    command = list(build['records'][variant]['linkCommand'])
    command[command.index(str(output / 'contract.cpp.o'))] = str(obj)
    exe = output / (variant + '-observed-probe')
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    result = subprocess.run([str(exe), str(fixture), *(['fixed'] if variant == 'corrected' else [])],
        capture_output=True, text=True, timeout=20)
    log = output / (variant + '-observed.log')
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    line = next(line for line in result.stdout.splitlines() if line.startswith('NESTED_SELECTION '))
    values = [int(value, 16) for value in line.split()[1:]]
    assert len(values) == 11
    if variant == 'corrected':
        assert values[2] == values[0] and values[3:7] == values[7:11]
    else:
        assert values[2] == values[1] and values[3] != values[7]
    results[variant] = {'values': values, 'executableSha256': sha(exe), 'logSha256': sha(log)}
(output / 'component.json').write_text(json.dumps({'result': 'LEGACY_SDK_CONTEXT_RESTORE_OBSERVED_FIXTURE_PASS',
    'buildSha256': sha(build_path), 'originalSdkComparisonSha256': sha(original_path),
    'inferredFixtureReportSha256': sha(fixture_report_path), 'fixtureSha256': sha(fixture),
    'probeSourceSha256': sha(source), 'probeObjectSha256': sha(obj), 'results': results,
    'recipeSha256': sha(Path(__file__)),
    'limits': ['Actual linked HLE before/after on observed pointer shape; some post-save controls are inferred, not a full original IRQ snapshot.',
        'Original SDK tail12cases; original full scheduler/thread transfer and physical nested IRQ behavior unverified.',
        'Legacy honors original SDK D4, configured return policy unchanged; no CPU ABI/second registry/forced PC or guard.',
        'Corrected whole game has not yet run; menu/audio/video acceptance pending.']}, indent=2) + '\n')
print('LEGACY_SDK_CONTEXT_RESTORE_OBSERVED_FIXTURE_PASS')
print('baselinePC', hex(results['baseline']['values'][3]), 'correctedPC', hex(results['corrected']['values'][3]))
