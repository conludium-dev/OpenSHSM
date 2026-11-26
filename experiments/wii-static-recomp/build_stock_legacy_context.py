"""Change one legacy HLE return policy; retain CPU ABI, guest functions and other runtime objects."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from stock_legacy_context_patch import adapt

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-cache-filtered'
output = root / 'window-legacy-context'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = base / 'build.json'
build = json.loads(build_path.read_text())
assert sha(base / 'OpenSHSMStockCacheFiltered') == build['executableSha256']
original = base / 'ios.cpp'
assert sha(original) == build['sourceSha256']
source = output / 'ios.cpp'
source.write_text(adapt(original.read_text()))
obj = output / 'ios.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(base), *build['arguments'],
    '-I', str(Path('experiments/wii-static-recomp').resolve()),
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = list(build['linkCommand'])
archive_old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
archive = output / 'libnwiiruntime.a'
shutil.copy2(archive_old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained_runtime = {}
for member in build['retainedRuntimeMembers']:
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(archive_old), member])
    assert before == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained_runtime[member] = hashlib.sha256(before).hexdigest()
command[command.index(str(archive_old))] = str(archive)
exe = output / 'OpenSHSMStockLegacyContext'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
probe_source = Path('experiments/wii-static-recomp/stock_legacy_context_contract.cpp').resolve()
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'main_output.cpp')
probe_obj = output / 'contract.cpp.o'
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(probe_source), '-o', str(probe_obj)],
    capture_output=True, check=True, timeout=60)
records = {}
for variant, runtime in [('baseline', archive_old), ('corrected', archive)]:
    probe_command = list(command)
    probe_command[probe_command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
    probe_command[probe_command.index(str(archive))] = str(runtime)
    probe_command.insert(1, str(probe_obj))
    probe = output / (variant + '-contract')
    probe_command[probe_command.index('-o') + 1] = str(probe)
    subprocess.run(probe_command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
    result = subprocess.run([str(probe), *(['baseline'] if variant == 'baseline' else [])],
        capture_output=True, text=True, timeout=20)
    (output / (variant + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = 'LEGACY_CONTEXT_BASELINE_POLICY_REPRODUCED 10' if variant == 'baseline' else 'LEGACY_CONTEXT_SDK_SELECTION_REGRESSION_PASS 12'
    assert expected in result.stdout
    records[variant] = {'executableSha256': sha(probe), 'logSha256': sha(output / (variant + '.log')),
        'linkCommand': probe_command}
(output / 'build.json').write_text(json.dumps({'result': 'LEGACY_CONTEXT_SDK_SELECTION_COMPONENT_PASS',
    'baseBuildSha256': sha(build_path), 'originalSourceSha256': sha(original), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command,
    'retainedRuntimeMembers': retained_runtime, 'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command
        if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
    'probeSourceSha256': sha(probe_source), 'records': records,
    'adapterSha256': sha(Path('experiments/wii-static-recomp/stock_legacy_context_patch.py')),
    'contextHeaderSha256': sha(base / 'stock_context_observation.h'),
    'recipeSha256': sha(Path(__file__)),
    'limits': ['Legacy return reads SDK-selected D4; configured dispatcher policy preserved.',
        'No CPU ABI/new context registry/forcedPC/guard/counter/clock/queue changes.',
        'Finite host selection fixtures; full original scheduler/nested hardware IRQ behavior remains unverified.',
        'No game run/menu/audio/video acceptance from component pass.']}, indent=2) + '\n')
print('LEGACY_CONTEXT_SDK_SELECTION_COMPONENT_PASS baseline10/corrected12; retained runtime', len(retained_runtime))
