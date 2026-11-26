"""Observe actual cache branch and exact guest context save/load, without changing state."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
base_path = root / 'window-fs-rename/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
output = root / 'headless-cache-irq-observe'
output.mkdir(exist_ok=True)
command = list(base['linkCommand'])
old_obj = next(Path(arg) for arg in command if Path(arg).name == 'output_38.cpp.o')
original = old_obj.with_suffix('')
record_path = original.with_name('output_38.cpp.record.json')
if record_path.exists():
    record = json.loads(record_path.read_text())
else:
    record_path = original.parent / 'build.json'
    inherited = json.loads(record_path.read_text())
    change = inherited['guestChanges']['output_38.cpp']
    original_record = json.loads((root / 'window-fp-guard/output_38.cpp.record.json').read_text())
    record = {**change, 'arguments': original_record['arguments']}
assert sha(original) == record['sourceSha256'] and sha(old_obj) == record['objectSha256']
text = original.read_text()
marker = 'loc_80212FF4: ;\n'
assert text.count(marker) == 1
start = text.index(marker)
end = text.index('loc_80212FF8: ;', start)
fragment = text[start:end]
anchor = '    if (process_pending_callbacks(ctx)) return;'
assert fragment.count(anchor) == 1
fragment = fragment.replace(anchor, '    openshsm::experiment::observe_cache_irq(ctx, 4);\n' + anchor
    + '\n    openshsm::experiment::observe_cache_irq(ctx, 5);')
text = '#include "stock_cache_irq_observation.h"\n' + text[:start] + fragment + text[end:]
source, obj = output / 'output_38.cpp', output / 'output_38.cpp.o'
source.write_text(text)
def compile_file(src, target, arguments, timeout):
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(src), '-o', str(target)], capture_output=True, text=True, timeout=timeout)
    (output / (target.name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
compile_file(source, obj, record['arguments'], 180)
command[command.index(str(old_obj))] = str(obj)
ios_original = root / 'window-legacy-context/ios.cpp'
ios_text = ios_original.read_text()
for phase in [0, 2, 3]:
    anchor = f'  stock_loading_observation::observe_context(ctx, {phase}, c);'
    assert ios_text.count(anchor) == 1
    ios_text = ios_text.replace(anchor, anchor + f'\n  openshsm::experiment::observe_cache_irq(ctx, {phase}, c);')
anchor = '    ctx.mmu.write32(c + 0x1A4 + i * 4, ctx.gqr[i]);\n}'
assert ios_text.count(anchor) == 1
ios_text = ios_text.replace(anchor, anchor[:-1] + '  openshsm::experiment::observe_cache_irq(ctx, 1, c);\n}')
ios_source, ios_obj = output / 'ios.cpp', output / 'ios.cpp.o'
ios_source.write_text('#include "stock_cache_irq_observation.h"\n' + ios_text)
ios_record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'ios.cpp')
compile_file(ios_source, ios_obj, ios_record['arguments'], 60)
old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old) == base['archiveSha256']
assert subprocess.check_output(['/usr/bin/ar', '-p', str(old), 'ios.cpp.o']) == (root / 'window-legacy-context/ios.cpp.o').read_bytes()
archive = output / 'libnwiiruntime.a'
shutil.copy2(old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(ios_obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(old)], text=True).splitlines():
    if member == 'ios.cpp.o' or member.startswith('__'):
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(old), member])
    assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(data).hexdigest()
command[command.index(str(old))] = str(archive)
exe = output / 'OpenSHSMStockCacheIRQObserve'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
probe_source, probe_obj = public / 'stock_cache_irq_probe.cpp', output / 'probe.cpp.o'
compile_file(probe_source, probe_obj, record['arguments'], 60)
probe_command = list(command)
probe_command[probe_command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
probe_command.insert(1, str(probe_obj))
probe = output / 'cache-probe'
probe_command[probe_command.index('-o') + 1] = str(probe)
subprocess.run(probe_command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'CACHE_FLUSH_NATIVE_NO_IRQ_PASS64' in result.stdout, result.stderr
(output / 'build.json').write_text(json.dumps({'result': 'CACHE_IRQ_OBSERVER_BUILT_EXECUTION_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'originalRecordSha256': sha(record_path), 'iosOriginalSha256': sha(ios_original), 'iosSourceSha256': sha(ios_source),
    'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command,
    'dependencies': {str(p): sha(p) for p in [Path(__file__).resolve(), public / 'stock_cache_irq_observation.h', probe_source]},
    'probeExecutableSha256': sha(probe), 'probeLogSha256': sha(output / 'probe.log'),
    'retainedRuntimeMembers': retained, 'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command
        if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a') and arg != str(obj) and arg != str(archive)},
    'limits': ['Bounded512normal/64unusual per phase at cache callback seam and exact save/load points; RAM-only reads.',
        'Existing context/CTR/callback/cache/renderer untouched; observer timing not original timing.',
        'No video performance, visual acceptance or IRQ root-cause proof from build.']}, indent=2) + '\n')
print('CACHE_IRQ_OBSERVER_BUILT_EXECUTION_UNVERIFIED')
