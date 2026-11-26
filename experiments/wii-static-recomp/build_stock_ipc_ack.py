"""Build an isolated pending-request ACK variant; leave the stock baseline and all guest objects unchanged."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import shutil
import subprocess

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
build = root / 'export/build'
output = root / 'ipc-ack'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(project / 'experiments/wii-static-recomp/audit_stock_baseline.py')], check=True)
original = root / 'export/nWiiRuntime/src/hw/hw_ipc.cpp'
text = original.read_text()
before = '  ipc_arm_msg  = virt_addr & 0x1FFFFFFF;\n  ipc_arm_ctrl = 0x00000003;'
after = '  if (result != -0x70000001) {\n    ipc_arm_msg = virt_addr & 0x1FFFFFFF;\n  }\n  ipc_arm_ctrl = 0x00000003;'
assert text.count(before) == 1 and text.count('ipc_ppc_ctrl |= 0x2C;') == 1
source = output / 'hw_ipc.cpp'
source.write_text(text.replace(before, after).replace('ipc_ppc_ctrl |= 0x2C;', 'ipc_ppc_ctrl |= 0x22;'))
flags = (build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
obj = output / 'hw_ipc.cpp.o'
result = subprocess.run([compiler, *arguments, '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
base_archive = build / 'nWiiRuntime/libnwiiruntime.a'
archive = output / 'libnwiiruntime.a'
base_hash = sha(base_archive)
members = subprocess.check_output(['/usr/bin/ar', '-t', str(base_archive)], text=True).splitlines()
assert members.count(obj.name) == 1
shutil.copy2(base_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
assert subprocess.check_output(['/usr/bin/ar', '-t', str(archive)], text=True).splitlines() == members
unchanged = {}
for member in members:
    if member == obj.name or member.startswith('__.SYMDEF'):
        continue
    old = subprocess.check_output(['/usr/bin/ar', '-p', str(base_archive), member])
    new = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert old == new, member
    unchanged[member] = hashlib.sha256(old).hexdigest()
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
index = command.index('-o') + 1
exe = output / 'OpenSHSMStockIPCAck'
command[index] = str(exe)
assert command.count('nWiiRuntime/libnwiiruntime.a') == 1
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
assert sha(base_archive) == base_hash
(output / 'build.json').write_text(json.dumps({'result': 'PENDING_IPC_ACK_VARIANT_BUILT_EXECUTION_PENDING',
    'builderSha256': sha(Path(__file__)), 'baseSourceSha256': sha(original), 'sourceSha256': sha(source),
    'baseArchiveSha256': base_hash, 'archiveSha256': sha(archive), 'executableSha256': sha(exe),
    'unchangedRuntimeMembers': unchanged, 'retainedObjects': {item: sha(build / item) for item in command if item.endswith('.cpp.o')},
    'limits': ['Two host IPC changes: pending request not published as ARM reply; ACK uses bit2 rather than reply bit4.',
        'Original ISR masks14/22 and stock premature-callback trace provide evidence; full runtime behavior requires execution.',
        'No forced guest queue bits, callback/free, clock or deadline changes; all75 guest objects retained.']}, indent=2) + '\n')
print('Built isolated pending-ACK variant; all guest objects and', len(unchanged), 'other runtime members unchanged')
