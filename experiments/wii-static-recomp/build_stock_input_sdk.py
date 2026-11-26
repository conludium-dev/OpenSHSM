"""Build a private input-bound variant; retain original runtime and all other guest objects."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_input_sdk_patch import adapt

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-input-sdk'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
legacy_path = root / 'window-legacy-context/build.json'
snapshot_path = root / 'input-snapshot-research/build.json'
legacy = json.loads(legacy_path.read_text())
snapshot = json.loads(snapshot_path.read_text())
assert sha(root / 'input-snapshot-research/libnwiiruntime.a') == snapshot['archiveSha256']
for path, expected in legacy['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected, path
arguments = snapshot['arguments']
command = list(legacy['linkCommand'])
archive_old = next(arg for arg in command if Path(arg).name == 'libnwiiruntime.a')
command[command.index(archive_old)] = str(root / 'input-snapshot-research/libnwiiruntime.a')
compiled = []
for name in ['output_1.cpp', 'output_44.cpp']:
    original_obj = next(Path(arg) for arg in command if Path(arg).name == name + '.o')
    original = original_obj.with_suffix('')
    record = json.loads(original.with_name(name + '.record.json').read_text())
    assert sha(original) == record['sourceSha256'] and sha(original_obj) == record['objectSha256']
    source, obj = output / name, output / (name + '.o')
    source.write_text(adapt(original.read_text(), name))
    guest_arguments = ['-I', str(root / 'input-snapshot-research/include'), *record['arguments']]
    dependencies = {str(path): sha(path) for path in [public / 'stock_input_sdk_bridge.h',
        public / 'stock_input_sample_bridge.h', public / 'stock_input_connection_bridge.h',
        root / 'input-snapshot-research/include/input/input_manager.h']}
    cache_path = output / (name + '.cache.json')
    cache_key = {'arguments': guest_arguments, 'sourceSha256': sha(source), 'dependencies': dependencies,
        'upstreamRecordSha256': sha(original.with_name(name + '.record.json'))}
    cached = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if cached.get('key') != cache_key or not obj.exists() or cached.get('objectSha256') != sha(obj):
        result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *guest_arguments,
            '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / (name + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        cache_path.write_text(json.dumps({'key': cache_key, 'objectSha256': sha(obj)}, indent=2) + '\n')
    command[command.index(str(original_obj))] = str(obj)
    compiled.append({'source': name, 'originalSourceSha256': sha(original), 'sourceSha256': sha(source),
        'objectSha256': sha(obj), 'originalObjectSha256': sha(original_obj)})
    print('Compiled input boundary', name, flush=True)
exe = output / 'OpenSHSMStockInputSDK'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
probe_source = public / 'stock_input_sdk_probe.cpp'
probe_obj = output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(probe_source), '-o', str(probe_obj)], capture_output=True, text=True, timeout=60)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
probe_command = list(command)
main_obj = root / 'window-quantization/main.cpp.o'
probe_command[probe_command.index(str(main_obj))] = str(root / 'window-quantization/contract-entry.cpp.o')
probe_command.insert(1, str(probe_obj))
probe = output / 'input-sdk-probe'
probe_command[probe_command.index('-o') + 1] = str(probe)
subprocess.run(probe_command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'PC_INPUT_SDK_INTEGRATION_PASS' in result.stdout, (result.returncode, result.stdout, result.stderr)
(output / 'build.json').write_text(json.dumps({'result': 'PC_INPUT_SDK_COMPONENT_PASS_BOOT_UNVERIFIED',
    'baseBuildSha256': sha(legacy_path), 'snapshotBuildSha256': sha(snapshot_path), 'compiled': compiled,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_input_sdk_patch.py',
        public / 'stock_input_sdk_bridge.h', public / 'stock_input_sample_bridge.h', public / 'stock_input_connection_bridge.h']},
    'linkCommand': command, 'executableSha256': sha(exe), 'probeSourceSha256': sha(probe_source),
    'probeObjectSha256': sha(probe_obj), 'probeSha256': sha(probe), 'logSha256': sha(output / 'probe.log'),
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and Path(arg).parent != output},
    'limits': ['Controlled source invokes patched original game sampler and original copying; not a game-window/hardware test.',
        'Primary keyboard virtual extension and provider status are PC adaptation, not Wii readiness/raw calibration equivalence.',
        'Only explicit recovered SDK entry PCs replaced; original continuation bodies retained.',
        'No live boot/menu or real input timing acceptance from this component result.']}, indent=2) + '\n')
print('PC_INPUT_SDK_COMPONENT_PASS_BOOT_UNVERIFIED')
