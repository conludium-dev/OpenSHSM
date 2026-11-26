"""Test actual patched IPC object with original MMIO dispatcher; IOS producer is a contract fixture."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
output = root / 'ipc-queue'
build = root / 'export/build'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((output / 'build.json').read_text())
assert manifest['sourceSha256'] == sha(output / 'hw_ipc.cpp')
assert manifest['executableSha256'] == sha(output / 'OpenSHSMStockIPCQueue')
assert manifest['baseArchiveSha256'] == sha(build / 'nWiiRuntime/libnwiiruntime.a')
for name, digest in manifest['retainedObjects'].items():
    assert sha(build / name) == digest
flags = (build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
recipe = project / 'experiments/wii-static-recomp/ipc_queue_contract.cpp'
dispatcher = root / 'export/nWiiRuntime/src/hw/mmio_dispatcher.cpp'
exe = output / 'ipc-queue-contract'
subprocess.run([compiler, *arguments, str(recipe), str(dispatcher), str(output / 'hw_ipc.cpp.o'), '-o', str(exe)], check=True, timeout=60)
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
assert result.returncode == 0, result.stdout + result.stderr
run = json.loads((root / 'ipc-queue-headless-result.json').read_text())
log = root / 'ipc-queue-headless.log'
assert run['executableSha256'] == manifest['executableSha256']
assert run['logSha256'] == sha(log)
assert run['deadlineReached'] and run['terminalReturncode'] == -15
text = log.read_text()
assert '[USB] HCI command opcode 0xc43' in text
assert '[GX] WGP write32' in text
assert '[Sample] pc=0x8022ced4' in text
(output / 'audit.json').write_text(json.dumps({
    'result': 'IPC_QUEUE_CONTRACT_AND_FULL_STARTUP_PROGRESS_PASS',
    'contract': result.stdout, 'contractSha256': sha(recipe),
    'runLogSha256': sha(log), 'retainedObjects': len(manifest['retainedObjects']),
    'limits': ['IOS producer mocked only in focused contract; whole runtime run uses actual upstream devices.',
        'Startup reaches GX and waits on audio sample counter, not first-screen or physical Wii proof.']
}, indent=2) + '\n')
print(result.stdout.strip())
print('Full startup advanced through HCI initialization to GX; no graphical acceptance')
