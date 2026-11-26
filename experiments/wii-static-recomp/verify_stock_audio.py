"""Test actual AI and IPC objects with deterministic host time, then inspect full boot separately."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--natural-alarms', action='store_true')
args = parser.parse_args()

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
variant = 'ipc-natural' if args.natural_alarms else 'ipc-audio'
output = root / variant
build = root / 'export/build'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((output / 'build.json').read_text())
assert manifest['audioEnabled']
assert manifest['audioSourceSha256'] == sha(output / 'hw_ai.cpp')
assert manifest['sourceSha256'] == sha(output / 'hw_ipc.cpp')
assert manifest['executableSha256'] == sha(output / ('OpenSHSMStockIPCNatural' if args.natural_alarms else 'OpenSHSMStockIPCAudio'))
if args.natural_alarms:
    assert manifest['naturalAlarms']
    original = (root / 'export/nWiiRuntime/src/hle/ios.cpp').read_text()
    start = original.index('      {\n          static uint32_t dec_same_pc_count = 0;')
    end = original.index('      static uint32_t dcount = 0;', start)
    assert (output / 'ios.cpp').read_text() == original[:start] + original[end:]
    assert sha(output / 'ios.cpp') == manifest['iosSourceSha256']
assert manifest['baseArchiveSha256'] == sha(build / 'nWiiRuntime/libnwiiruntime.a')
for name, digest in manifest['retainedObjects'].items():
    assert sha(build / name) == digest
flags = (build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
dispatcher = root / 'export/nWiiRuntime/src/hw/mmio_dispatcher.cpp'
records = {}
for label, recipe_name, objects in (
    ('audio', 'stock_audio_contract.cpp', ['hw_ai.cpp.o', 'hw_ipc.cpp.o']),
    ('ipc', 'ipc_queue_contract.cpp', ['hw_ipc.cpp.o']),
):
    recipe = project / 'experiments/wii-static-recomp' / recipe_name
    exe = output / (label + '-contract')
    subprocess.run([compiler, *arguments, str(recipe), str(dispatcher),
        *[str(output / name) for name in objects], '-o', str(exe)], check=True, timeout=60)
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    records[label] = {'output': result.stdout, 'recipeSha256': sha(recipe)}
    print(result.stdout.strip())
label = 'ipc-natural-headless-gx' if args.natural_alarms else 'ipc-audio-headless'
run = json.loads((root / (label + '-result.json')).read_text())
log = root / (label + '.log')
assert run['executableSha256'] == manifest['executableSha256']
assert run['logSha256'] == sha(log)
assert run['deadlineReached'] and run['terminalReturncode'] == -15
text = log.read_text()
if args.natural_alarms:
    assert 'force-expired alarm' not in text
assert '[ GPU Hang detected ]' in text
assert '_RwDlTokenCurrent   0x0003' in text
assert 'GX Last Seen        0x0002' in text
assert '[Sample] pc=0x8022ced4' not in text
(output / 'contract.json').write_text(json.dumps({
    'result': 'AUDIO_AND_IPC_FOCUSED_CONTRACT_PASS', 'contracts': records,
    'runLogSha256': sha(log), 'nextBlocker': 'Original GPU hang report: next token3/token2 seen; loss of token3 not established',
    'retainedObjects': len(manifest['retainedObjects']),
    'limits': ['Clock and IOS producer mocked in focused tests, not original execution or audio output proof.',
        'Counter uses host microsecond time and nominal32/48kHz, not cycle-exact Wii timing.']
}, indent=2) + '\n')
print('Full boot passed audio initialization and reached original GPU hang diagnostic; first screen unproven')
