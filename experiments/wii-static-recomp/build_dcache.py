"""Enable verified DCE memory model incrementally; preserve previous module/proofs."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
base = Path('work/private-game/static-recomp/mass-memory')
output = Path('work/private-game/static-recomp/mass-dcache')
output.mkdir(exist_ok=True)
module = Path('work/private-game/static-recomp/mass-current')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((base / 'lowering.json').read_text())
assert lowering['headerSha256'] == sha(experiment / 'memory_frontend.h')
assert json.loads(Path('work/private-game/static-recomp/dolphin-conflict-probe/comparison.json').read_text())['result'] == 'ACCURATE_CACHE_CONFLICT_TRACE_MATCH'
objects, records = [], []
changes = 0
for record in lowering['records']:
    source = base / record['file']
    obj = base / (record['file'] + '.o')
    assert sha(source) == record['sourceSha256'] and sha(obj) == record['objectSha256']
    text = source.read_text()
    count = text.count('nwii::runtime::experiment_write_hid0_icache(ctx,')
    if count:
        source = output / record['file']
        source.write_text(text.replace('nwii::runtime::experiment_write_hid0_icache(ctx,', 'nwii::runtime::experiment_write_hid0_dcache(ctx,'))
        obj = output / (record['file'] + '.o')
        result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', str(experiment / 'dcache_adapter.h'),
                                 '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(module), '-c', str(source), '-o', str(obj)],
                                capture_output=True, text=True, timeout=180)
        (output / (record['file'] + '.build.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
    objects.append(str(obj))
    records.append({'file': record['file'], 'directory': str(source.parent), 'sourceSha256': sha(source),
                    'objectSha256': sha(obj), 'changedSites': count})
    changes += count
assert changes == 7 and sum(record['changedSites'] > 0 for record in records) == 2
report = {'result': 'COMPILED_DCE_NOT_ORACLE_VERIFIED', 'records': records, 'changes': changes,
          'baseLoweringSha256': sha(base / 'lowering.json'), 'adapterSha256': sha(experiment / 'dcache_adapter.h'),
          'scriptSha256': sha(Path(__file__))}
(output / 'lowering.json').write_text(json.dumps(report, indent=2) + '\n')
policy = Path('work/private-game/static-recomp/mass-icache/boot-quarantine.tsv')
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
                         '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(module), '-I', str(upstream / 'nWiiRuntime/include'),
                         '-I', str(upstream / 'nWiiAnalyzer/include'), str(experiment / 'dcache_boot.cpp'),
                         str(experiment / 'processor_adapter.cpp'), str(upstream / 'nWiiRuntime/src/core/loader.cpp'),
                         *objects, '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout, (result.returncode, result.stdout[-3000:], result.stderr[-1000:])
report = {'result': 'DCE_BOOT_REQUIRES_ORACLE_COMPARISON', 'stdout': result.stdout, 'exitCode': result.returncode,
          'executableSha256': sha(exe), 'loweringSha256': sha(output / 'lowering.json'),
          'wrapperSha256': sha(experiment / 'dcache_boot.cpp'), 'baseWrapperSha256': sha(experiment / 'mass_boot.cpp'),
          'policySha256': sha(policy)}
(output / 'boot.json').write_text(json.dumps(report, indent=2) + '\n')
print('DCE candidate:7sites/2batches rebuilt/123objects reused; boundary unverified', flush=True)
print(result.stdout[-6000:], flush=True)
