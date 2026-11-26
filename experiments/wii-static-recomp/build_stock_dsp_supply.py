"""Observe the existing DSP producer and pull under its own mutex; no scheduling/PCM changes."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-dsp-supply'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-debug-overlay/build.json'
parent = json.loads(parent_path.read_text())
for path, expected in {**parent['dependencies'], **parent['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
command = list(parent['linkCommand'])
old_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(old_archive) == parent['archiveSha256']
records = json.loads((root / 'window-quantization/build.json').read_text())['compiled']
record = next(row for row in records if row['source'] == 'hw_dsp.cpp')
original = root / 'window-quantization/hw_dsp.cpp'
assert sha(original) == record['sourceSha256']
members = [member for member in subprocess.run(['/usr/bin/ar', 't', str(old_archive)],
    capture_output=True, check=True, text=True).stdout.splitlines() if member.endswith('.o')]
assert members and len(members) == len(set(members))
before = {member: hashlib.sha256(subprocess.run(['/usr/bin/ar', 'p', str(old_archive), member],
    capture_output=True, check=True).stdout).hexdigest() for member in members}
assert before['hw_dsp.cpp.o'] == record['objectSha256']
text = original.read_text()
patches = [
    ('    if (n < frames)\n', '    openshsm::experiment::dsp_supply_observer.pulled(frames, n, have);\n    if (n < frames)\n'),
    ('        if (adma_ring.size() < 32000 * 2) {',
        '        const auto supply_before = adma_ring.size() / 2;\n'
        '        const bool supply_admitted = adma_ring.size() < 32000 * 2;\n'
        '        if (supply_admitted) {'),
    ('        }\n    }\n    \n    dsp_control |= 0x0008;',
        '        }\n        openshsm::experiment::dsp_supply_observer.produced(bytes / 4, supply_before,\n'
        '            adma_ring.size() / 2, late, ctx.tb_freq / 200, supply_admitted);\n'
        '    }\n    \n    dsp_control |= 0x0008;')]
for old, new in patches:
    assert text.count(old) == 1, old
    text = text.replace(old, new)
text = '#include "stock_dsp_supply.h"\n' + text
source, obj = output / 'hw_dsp.cpp', output / 'hw_dsp.cpp.o'
source.write_text(text)
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
archive = output / 'libnwiiruntime.a'
archive.write_bytes(old_archive.read_bytes())
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], capture_output=True, check=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], capture_output=True, check=True)
after = {member: hashlib.sha256(subprocess.run(['/usr/bin/ar', 'p', str(archive), member],
    capture_output=True, check=True).stdout).hexdigest() for member in members}
assert all(after[member] == digest for member, digest in before.items() if member != 'hw_dsp.cpp.o')
command[command.index(str(old_archive))] = str(archive)
exe = output / 'OpenSHSMStockDSPSupply'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
scheduler = next(row for row in records if row['source'] == 'event_scheduler.cpp')
scheduler_source = root / 'window-quantization/event_scheduler.cpp'
assert before['event_scheduler.cpp.o'] == scheduler['objectSha256'] and sha(scheduler_source) == scheduler['sourceSha256']
(output / 'build.json').write_text(json.dumps({'result': 'PRIVATE_DSP_SUPPLY_BUILT_LIVE_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'sourceSha256': sha(source), 'baseSourceSha256': sha(original),
    'objectSha256': sha(obj), 'executableSha256': sha(exe), 'archiveSha256': sha(archive), 'linkCommand': command,
    'patches': patches, 'retainedArchiveMembers': before, 'derivedArchiveMembers': after,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_dsp_supply.h', scheduler_source]},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o'},
    'limits': ['Existing DSP mutex/producer/pull/PCM/event scheduling unchanged; one runtime object observed.',
        'All75guest/main-overlay/other runtime members retained; no second queue or audio buffering fix.']}, indent=2) + '\n')
print('PRIVATE_DSP_SUPPLY_BUILT_LIVE_UNVERIFIED')
