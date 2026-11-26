"""Measure the retained vendor readback counterexample; do not admit unverified requests."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'ipc-message-gap'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_ipc_message_dolphin.py')], check=True)
oracle_path = root / 'dolphin-ipc-message/comparison.json'
oracle = json.loads(oracle_path.read_text())
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sources = [experiment / 'ipc_message_gap_probe.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp']
exe = output / 'ipc-message-gap-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O2', '-include', 'bit',
    '-I', str(experiment), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=60)
(output / 'build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
(output / 'native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and not result.stderr
rows = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines()]
assert rows == [[index, 0x135e0020, 0x135e0020, 0x38] for index in range(16)]
assert oracle['invalidRegisterReads'] == [0] * 16
inputs = sources + [experiment / 'ipc_reset_backend.cpp', experiment / 'ipc_reset_backend.h', runtime / 'src/hw/hw_ipc.cpp']
(output / 'comparison.json').write_text(json.dumps({'result': 'VENDOR_MESSAGE_INVALID_READ16_COUNTEREXAMPLES_CONFIRMED',
    'verifierSha256': sha(Path(__file__)), 'oracleSha256': sha(oracle_path),
    'sourceHashes': {str(path): sha(path) for path in inputs}, 'executableSha256': sha(exe),
    'logSha256': sha(output / 'native.log'), 'counterexamples': 16,
    'reference': 'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/HW/WII_IPC.cpp',
    'limits': ['Diagnostic vendor MMIO, not a native whole-function port or internal original-latch proof.',
        'No source/backend/frontend permission change or IOS requests.']}, indent=2) + '\n')
print('PASS16 vendor message-read counterexamples: pointer vs original invalid-read zero; no request sent')
