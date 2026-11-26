"""Reuse the current compiled module for complete original UART execution."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'uart-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_uart_dolphin.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_exi_getid_native.py')], check=True)
metadata = json.loads((private / 'exi-getid-native/execution.json').read_text())
for row in metadata['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
(output / 'loader-bat-seed.h').write_bytes((private / 'exi-getid-native/loader-bat-seed.h').read_bytes())
host = output / 'uart-host.cpp'
body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')
host.write_text(body + '\n' + (experiment / 'uart_host.cpp').read_text())
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp',
    runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'uart-probe'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources),
    *[row['object'] for row in metadata['records']], '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
(output / 'build.json').write_text(json.dumps({'result': 'UART_COMPILED_EXECUTION_UNVERIFIED', 'returnCode': result.returncode,
    'builderSha256': sha(Path(__file__)), 'hostSourceSha256': sha(experiment / 'uart_host.cpp'),
    'baseExecutionSha256': sha(private / 'exi-getid-native/execution.json'), 'executableSha256': sha(exe),
    'oracleSha256': sha(private / 'dolphin-uart/comparison.json'), 'sourceHashes': {str(path): sha(path) for path in sources},
    'backendSha256': sha(experiment / 'exi_getid_backend.h')}, indent=2) + '\n')
print(result.stdout[-1500:] + result.stderr)
assert result.returncode == 0, 'Original native UART has not completed'
