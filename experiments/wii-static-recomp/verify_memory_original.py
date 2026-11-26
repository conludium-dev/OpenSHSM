"""Execute an original function in the full routed module; retain independent PPC oracle scope."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-memory'
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'audit_result.py')], check=True)
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['headerSha256'] == sha(experiment / 'memory_frontend.h')
objects = []
for record in lowering['records']:
    source = output / record['file']
    obj = output / (record['file'] + '.o')
    assert record['sourceSha256'] == sha(source) and record['objectSha256'] == sha(obj)
    objects.append(str(obj))
exe = output / 'memory-original-probe'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER',
                         '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
                         '-I', str(private / 'mass-current'), '-I', str(upstream / 'nWiiRuntime/include'),
                         '-I', str(upstream / 'nWiiAnalyzer/include'), str(experiment / 'memory_original_probe.cpp'),
                         str(experiment / 'processor_adapter.cpp'), str(upstream / 'nWiiRuntime/src/core/loader.cpp'),
                         *objects, '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'original-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'original-execution.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
rows = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('MEMORY_ORIGINAL ')]
oracle_path = private / 'execution-unicorn-vs-nwii.json'
oracle = json.loads(oracle_path.read_text())
assert oracle['result'] == 'PASS' and oracle['cases'] == 536
assert len(rows) == 1072
dirty_changes = 0
for cached in range(2):
    for row, original in zip(rows[cached * 536:(cached + 1) * 536], oracle['records']):
        mode, value, direction, observed, abi, calls, backing, written = row
        assert [mode, value, direction] == [cached, original['prior'], original['direction']]
        assert observed == written == original['ppcValue'] and abi == 1 and calls == 3, row
        assert backing == (value if cached else observed), row
        dirty_changes += int(cached and backing != observed)
assert dirty_changes > 0
report = {'result': 'ORIGINAL_FUNCTION_CACHE_FRONTEND_BOUNDED_PASS', 'function': '0x800F3E60',
          'casesPerMode': 536, 'nativeExecutions': len(rows), 'dirtyChangedCases': dirty_changes,
          'oracleSha256': sha(oracle_path), 'loweringSha256': sha(output / 'lowering.json'),
          'probeSourceSha256': sha(experiment / 'memory_original_probe.cpp'), 'scriptSha256': sha(Path(__file__)),
          'executableSha256': sha(exe),
          'limits': ['Original PPC arithmetic/ABI oracle uses flat controlled memory; cache visibility expectations use the separately measured Dolphin alias/writeback model.',
                     'HID0.DCE is supplied by the test fixture. Native DCEnable and whole cache-enabled bootstrap remain unverified.',
                     'Conflict replacement, DMA, OS/IOS/GX/menu and physical Wii execution remain unverified.']}
(output / 'original-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS original full-module consumer:1072executions/536PPCcases per mode/{dirty_changes}dirty changes; DCE bootstrap pending')
