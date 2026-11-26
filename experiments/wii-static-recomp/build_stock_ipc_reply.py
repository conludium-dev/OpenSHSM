"""Correct reply headers at the existing private publication boundary only."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
base_path = root / 'window-ipc-vector-observe/build.json'
base = json.loads(base_path.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected, path
output = root / 'window-ipc-reply'
output.mkdir(exist_ok=True)
original = root / 'window-quantization/hw_ipc.cpp'
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled']
    if row['source'] == 'hw_ipc.cpp')
assert sha(original) == record['sourceSha256']
text = original.read_text()
marker = 'static void complete_reply(uint32_t address) {\n'
assert text.count(marker) == 1
text = '#include "stock_ipc_reply.h"\n#include <stdexcept>\n' + text.replace(marker, marker +
    '    if (!g_mmu || !openshsm::experiment::prepare_ipc_reply(*g_mmu, address)) {\n'
    '        throw std::runtime_error("Invalid IPC completion header/backing");\n    }\n')
source, obj = output / 'hw_ipc.cpp', output / 'hw_ipc.cpp.o'
source.write_text(text)
def compile_file(src, target):
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
        '-c', str(src), '-o', str(target)], capture_output=True, text=True, timeout=60)
    (output / (target.name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
compile_file(source, obj)
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
archive = output / 'libnwiiruntime.a'
shutil.copy2(old, archive)
assert subprocess.check_output(['/usr/bin/ar', '-p', str(old), 'hw_ipc.cpp.o']) == (root / 'window-quantization/hw_ipc.cpp.o').read_bytes()
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
retained = {}
for name in subprocess.check_output(['/usr/bin/ar', '-t', str(old)], text=True).splitlines():
    if name == 'hw_ipc.cpp.o' or name.startswith('__'):
        continue
    member = subprocess.check_output(['/usr/bin/ar', '-p', str(old), name])
    assert member == subprocess.check_output(['/usr/bin/ar', '-p', str(archive), name])
    retained[name] = hashlib.sha256(member).hexdigest()
command[command.index(str(old))] = str(archive)
exe = output / 'OpenSHSMStockIPCReply'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
probe_source, probe_obj = public / 'stock_ipc_reply_probe.cpp', output / 'probe.cpp.o'
compile_file(probe_source, probe_obj)
probe_command = list(command)
probe_command[probe_command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
probe_command.insert(1, str(probe_obj))
records = {}
for name, runtime, flags, expected in [('baseline', old, ['baseline'], 'BASELINE_REPLY_HEADER_BUG_REPRODUCED'),
        ('corrected', archive, [], 'IPC_REPLY_COMPONENT_PASS')]:
    cmd = list(probe_command)
    cmd[cmd.index(str(archive))] = str(runtime)
    probe = output / (name + '-probe')
    cmd[cmd.index('-o') + 1] = str(probe)
    subprocess.run(cmd, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
    result = subprocess.run([str(probe), *flags], capture_output=True, text=True, timeout=20)
    log = output / (name + '.log')
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and expected in result.stdout, (name, result.returncode, result.stdout, result.stderr)
    records[name] = {'result': expected, 'executableSha256': sha(probe), 'logSha256': sha(log)}
(output / 'build.json').write_text(json.dumps({'result': 'IPC_REPLY_COMPONENT_PASS_LIVE_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'sourceSha256': sha(source), 'originalSourceSha256': sha(original),
    'objectSha256': sha(obj), 'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command,
    'records': records, 'retainedRuntimeMembers': retained,
    'dependencies': {str(p): sha(p) for p in [Path(__file__).resolve(), public / 'stock_ipc_reply.h', probe_source]},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(archive)},
    'sources': ['https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/IOS.h',
        'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/IOS.cpp'],
    'limits': ['Header serialization only; existing result writer, request dispatch and completion FIFO retained.',
        'Async publication uses synthetic already-completed device packet, not full USB lifecycle.',
        'No hardware/whole original consumer/live profile/render/persistence acceptance from component.']}, indent=2) + '\n')
print('IPC_REPLY_COMPONENT_PASS_LIVE_UNVERIFIED retained runtime', len(retained))
