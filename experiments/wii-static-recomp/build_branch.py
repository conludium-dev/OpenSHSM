"""Apply one generic backedge lowering across the existing complete module."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import subprocess
from branch_lowering import lower

experiment = Path('experiments/wii-static-recomp')
base = Path('work/private-game/static-recomp/mass-l2')
output = Path('work/private-game/static-recomp/mass-branch')
output.mkdir(exist_ok=True)
module = Path('work/private-game/static-recomp/mass-current')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
metadata = json.loads((base / 'lowering.json').read_text())
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'

def compile_record(record):
    source = Path(record['directory']) / record['file']
    obj = Path(str(source) + '.o')
    assert sha(source) == record['sourceSha256'] and sha(obj) == record['objectSha256']
    modified, changes = lower(source.read_text(), dol)
    if changes:
        source = output / record['file']
        source.write_text(modified)
        obj = Path(str(source) + '.o')
        result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', str(experiment / 'l2_adapter.h'),
                                 '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(module), '-c', str(source), '-o', str(obj)],
                                capture_output=True, text=True, timeout=180)
        (output / (record['file'] + '.build.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
    print(record['file'], len(changes), flush=True)
    return {'file': record['file'], 'directory': str(source.parent), 'sourceSha256': sha(source),
            'objectSha256': sha(obj), 'inputDirectory': record['directory'], 'inputSha256': record['sourceSha256'], 'changes': changes}

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    records = list(executor.map(compile_record, metadata['records']))
report = {'result': 'COMPILED_BRANCH_PATHS_NOT_ORACLE_VERIFIED', 'records': records,
          'sites': sum(len(record['changes']) for record in records),
          'baseLoweringSha256': sha(base / 'lowering.json'), 'scriptSha256': sha(Path(__file__)),
          'lowererSha256': sha(experiment / 'branch_lowering.py')}
(output / 'lowering.json').write_text(json.dumps(report, indent=2) + '\n')
wrapper = base / 'boot-wrapper.cpp'
policy = base / 'boot-quarantine.tsv'
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
                         '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(experiment), '-I', str(module), '-I', str(upstream / 'nWiiRuntime/include'),
                         '-I', str(upstream / 'nWiiAnalyzer/include'), str(wrapper), str(experiment / 'processor_adapter.cpp'),
                         str(upstream / 'nWiiRuntime/src/core/loader.cpp'),
                         *[str(Path(record['directory']) / (record['file'] + '.o')) for record in records], '-o', str(exe)],
                        capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout
(output / 'boot.json').write_text(json.dumps({'result': 'BRANCH_BOOT_ENDPOINT_UNVERIFIED', 'stdout': result.stdout,
                                            'executableSha256': sha(exe), 'loweringSha256': sha(output / 'lowering.json'),
                                            'wrapperSha256': sha(wrapper), 'policySha256': sha(policy)}, indent=2) + '\n')
print('Generic backedge sites:', report['sites'], flush=True)
print(result.stdout[-1800:], flush=True)
