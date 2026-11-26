"""Verify missing CP breakpoint path without treating mocked hardware contracts as original execution."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
from stock_cp_patch import adapt_cp

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
output = root / 'ipc-cpbp'
build = root / 'export/build'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((output / 'build.json').read_text())
original = root / 'export/nWiiRuntime/src/hw/hw_cp.cpp'
assert (output / 'hw_cp.cpp').read_text() == adapt_cp(original.read_text())
assert sha(output / 'hw_cp.cpp') == manifest['cpSourceSha256']
assert sha(original) == manifest['cpBaseSha256']
assert sha(output / 'OpenSHSMStockIPCCPBP') == manifest['executableSha256']
for name, digest in manifest['retainedObjects'].items():
    assert sha(build / name) == digest
flags = (build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
recipe = project / 'experiments/wii-static-recomp/stock_cp_contract.cpp'
dispatcher = root / 'export/nWiiRuntime/src/hw/mmio_dispatcher.cpp'
exe = output / 'cp-contract'
subprocess.run([compiler, *arguments, str(recipe), str(dispatcher), str(output / 'hw_cp.cpp.o'), '-o', str(exe)], check=True, timeout=60)
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
assert result.returncode == 0, result.stdout + result.stderr
label = 'ipc-cpbp-peek-gx'
run = json.loads((root / (label + '-result.json')).read_text())
log = root / (label + '.log')
assert run['executableSha256'] == manifest['executableSha256']
assert run['logSha256'] == sha(log)
assert run['deadlineReached'] and run['terminalReturncode'] == -15
text = log.read_text()
assert '[ GPU Hang detected ]' not in text
rows = [line.split(': ', 1)[1].split() for line in text.splitlines() if line.startswith('[Peek] 8052b220:')]
assert rows and any(row[11:13] == ['2', '2'] for row in rows)
window_label = 'ipc-cpbp-headless-gx-windowed-frame'
window_run = json.loads((root / (window_label + '-result.json')).read_text())
window_log = root / (window_label + '.log')
assert window_run['executableSha256'] == manifest['executableSha256']
assert window_run['logSha256'] == sha(window_log)
assert window_run['deadlineReached'] and window_run['terminalReturncode'] == -9
assert '[ GPU Hang detected ]' in window_log.read_text()
(output / 'contract.json').write_text(json.dumps({
    'result': 'CP_BREAKPOINT_CONTRACT_PASS', 'output': result.stdout,
    'headlessLogSha256': sha(log), 'windowedLogSha256': sha(window_log),
    'startup': 'Headless8s ring head=tail=2, no watchdog; windowed15s watchdog before initial GPU processing persists',
    'retainedObjects': len(manifest['retainedObjects']),
    'limits': ['Focused contract has null CPU and trap WGPIPE sink; tests registers/IRQ only, not FIFO drain or original Wii.',
        'Existing direct WGPIPE path still does not advance CP pointers; full ring behavior not proven.']
}, indent=2) + '\n')
print(result.stdout.strip())
print('Headless ring released both blocks; windowed startup watchdog remains, no first-screen claim')
