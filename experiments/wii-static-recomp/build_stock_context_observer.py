"""Add bounded read-only selection/save/load observations to the linked IOS object only."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import argparse
from stock_cache_observation import extend_header, adapt_guest, verify_sites

parser = argparse.ArgumentParser()
parser.add_argument('--cache', action='store_true')
parser.add_argument('--filtered-cache', action='store_true')
args = parser.parse_args()
args.cache = args.cache or args.filtered_cache

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-sdk-enable-resume'
output = root / ('window-cache-filtered' if args.filtered_cache else 'window-cache-observe' if args.cache else 'window-context-observe')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = base / 'build.json'
build = json.loads(build_path.read_text())
assert sha(base / 'OpenSHSMStockSDKEnableResume') == build['executableSha256']
command = list(build['linkCommand'])
archive_old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
original = root / 'window-fp-lazy-context/ios.cpp'
old_obj = original.with_suffix('.cpp.o')
assert subprocess.check_output(['/usr/bin/ar', '-p', str(archive_old), 'ios.cpp.o']) == old_obj.read_bytes()
text = original.read_text()
markers = [
    ('static void hle_save_context_to_guest(CPUContext &ctx, uint32_t c) {',
        '\n  stock_loading_observation::observe_context(ctx, 0, c);'),
    ('  if (c == 0)\n    return false;',
        '\n  stock_loading_observation::observe_context(ctx, 2, c);'),
    ('  ctx.msr = ctx.mmu.read32(c + 0x19C);',
        '\n  stock_loading_observation::observe_context(ctx, 3, c);')]
for marker, addition in markers:
    assert text.count(marker) == 1
    text = text.replace(marker, marker + addition)
marker = '    if (ctx.dispatch_saved_ctx) {'
assert text.count(marker) == 1
text = text.replace(marker, '    stock_loading_observation::observe_context(ctx, 1, ctx.dispatch_saved_ctx);\n' + marker)
source = output / 'ios.cpp'
source.write_text('#include "stock_context_observation.h"\n' + text)
header_path = Path('experiments/wii-static-recomp/stock_context_observation.h')
if args.cache:
    verify_sites(Path('work/private-game/disc/DATA/sys/main.dol').read_bytes())
    header_path = output / 'stock_context_observation.h'
    header_path.write_text(extend_header(Path('experiments/wii-static-recomp/stock_context_observation.h').read_text(), args.filtered_cache))
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'ios.cpp')
obj = output / 'ios.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-I', str(output), '-I', str(Path('experiments/wii-static-recomp').resolve()), '-c', str(source), '-o', str(obj)],
    capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
archive = output / 'libnwiiruntime.a'
shutil.copy2(archive_old, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(archive_old)], text=True).splitlines():
    if member.startswith('__.SYMDEF') or member == obj.name:
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(archive_old), member])
    assert data == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    retained[member] = hashlib.sha256(data).hexdigest()
command[command.index(str(archive_old))] = str(archive)
guest_changes = {}
if args.cache:
    for index in (11, 38):
        name = f'output_{index}.cpp'
        old = next(Path(arg) for arg in command if Path(arg).name == name + '.o')
        guest_source = output / name
        guest_source.write_text(adapt_guest(old.with_suffix('').read_text(), index))
        guest_obj = output / (name + '.o')
        guest_args = next(row['arguments'] for row in full['compiled'] if row['source'] == name)
        result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *guest_args,
            '-I', str(output), '-I', str(old.parent), '-I', str(Path('experiments/wii-static-recomp').resolve()),
            '-c', str(guest_source), '-o', str(guest_obj)], capture_output=True, text=True, timeout=60)
        (output / (name + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr
        command[command.index(str(old))] = str(guest_obj)
        guest_changes[name] = {'originalPath': str(old.with_suffix('')), 'originalSha256': sha(old.with_suffix('')),
            'sourceSha256': sha(guest_source), 'objectSha256': sha(guest_obj)}
exe = output / ('OpenSHSMStockCacheFiltered' if args.filtered_cache else 'OpenSHSMStockCacheObserver' if args.cache else 'OpenSHSMStockContextObserver')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
component = json.loads((root / 'context-restore-fixtures/component.json').read_text())
probe_command = list(component['linkCommand'])
probe_command[probe_command.index(str(archive_old))] = str(archive)
probe = output / 'context-observer-probe'
probe_command[probe_command.index('-o') + 1] = str(probe)
subprocess.run(probe_command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
prefix = output / 'component'
assert not prefix.with_name(prefix.name + '-contexts.jsonl').exists(), 'Preserve prior fixture captures'
env = dict(os.environ, NWII_THPDUMP=str(prefix))
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20, env=env)
(output / 'component.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'LINKED_CONTEXT_RESTORE_FIXTURES_PASS 8' in result.stdout
capture = prefix.with_name(prefix.name + '-contexts.jsonl')
rows = [json.loads(line) for line in capture.read_text().splitlines()]
assert len(rows) == 24 and {row['stage'] for row in rows} == {1, 2, 3}
assert sum(row['stage'] == 3 and row['pc'] == 0 for row in rows) == 4
cache_component = None
if args.cache:
    old_component = root / 'cache-invalidate-fixtures/native.json'
    cache_command = list(json.loads(old_component.read_text())['linkCommand'])
    for index in (11, 38):
        old = next(arg for arg in cache_command if Path(arg).name == f'output_{index}.cpp.o')
        cache_command[cache_command.index(old)] = str(output / f'output_{index}.cpp.o')
    old_archive = next(arg for arg in cache_command if Path(arg).name == 'libnwiiruntime.a')
    cache_command[cache_command.index(old_archive)] = str(archive)
    cache_probe = output / 'cache-probe'
    cache_command[cache_command.index('-o') + 1] = str(cache_probe)
    subprocess.run(cache_command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    cache_prefix = output / 'cache-component'
    cache_capture = output / 'cache-component-contexts.jsonl'
    assert not cache_capture.exists()
    result = subprocess.run([str(cache_probe)], capture_output=True, text=True, timeout=20,
        env=dict(os.environ, NWII_THPDUMP=str(cache_prefix)))
    (output / 'cache-component.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0
    assert result.stdout == (root / 'cache-invalidate-fixtures/probe.log').read_text()
    cache_rows = [json.loads(line) for line in cache_capture.read_text().splitlines()]
    assert {row['stage'] for row in cache_rows} == {4, 5, 6, 7}
    assert sum(row['stage'] == 4 for row in cache_rows) == 64
    assert sum(row['stage'] == 7 for row in cache_rows) == 60
    assert all(row['gpr4'] >= 0 and row['lr'] == 0x8009BB9C for row in cache_rows)
    cache_component = {'events': len(cache_rows), 'captureSha256': sha(cache_capture),
        'logSha256': sha(output / 'cache-component.log'), 'executableSha256': sha(cache_probe),
        'baselineNativeReportSha256': sha(old_component)}
(output / 'build.json').write_text(json.dumps({'result': 'CONTEXT_OBSERVER_COMPONENT_PASS',
    'baseBuildSha256': sha(build_path), 'originalSourceSha256': sha(original), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'headerSha256': sha(header_path), 'cache': args.cache,
    'filteredCache': args.filtered_cache,
    'guestChanges': guest_changes, 'cacheComponent': cache_component,
    'cacheAdapterSha256': sha(Path('experiments/wii-static-recomp/stock_cache_observation.py')) if args.cache else None,
    'archiveSha256': sha(archive), 'retainedRuntimeMembers': retained,
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(archive)
        and Path(arg).name not in {name + '.o' for name in guest_changes}},
    'linkCommand': command, 'executableSha256': sha(exe), 'probeSha256': sha(probe),
    'componentCaptureSha256': sha(capture), 'componentLogSha256': sha(output / 'component.log'),
    'recipeSha256': sha(Path(__file__)), 'arguments': arguments,
    'limits': ['Read-only host observer; cache mode per-stage budgets total<=7184,16reserved criticalzero records; timing can change.',
        'Eight linked restore fixtures/24observations, not original IRQ/thread scheduling or whole-game behavior.',
        'Guest context dump/private runtime only; no replacement state/forced PC/IRQ/readiness/guard.']}, indent=2) + '\n')
print('CONTEXT_OBSERVER_COMPONENT_PASS 8fixtures 24records; retained runtime', len(retained), 'cache', cache_component)
