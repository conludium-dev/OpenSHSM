"""Link the fully rerouted module while retaining the existing strict DCE/unknown-service gates."""
from pathlib import Path
import hashlib
import json
import subprocess

output = Path('work/private-game/static-recomp/mass-memory')
module = Path('work/private-game/static-recomp/mass-current')
base = Path('work/private-game/static-recomp/mass-icache')
experiment = Path('experiments/wii-static-recomp')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['filesCompiled'] == 125
objects = []
for record in lowering['records']:
    source = output / record['file']
    obj = output / (record['file'] + '.o')
    assert record['sourceSha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert record['objectSha256'] == hashlib.sha256(obj.read_bytes()).hexdigest()
    objects.append(str(obj))
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
                         '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(module), '-I', str(upstream / 'nWiiRuntime/include'),
                         '-I', str(upstream / 'nWiiAnalyzer/include'), str(experiment / 'memory_boot.cpp'),
                         str(experiment / 'processor_adapter.cpp'), str(upstream / 'nWiiRuntime/src/core/loader.cpp'),
                         *objects, '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'boot-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
policy = base / 'boot-quarantine.tsv'
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY pc=80212f80' in result.stdout, (result.returncode, result.stdout[-3000:], result.stderr[-1000:])
previous = json.loads((base / 'boot.json').read_text())
assert result.stdout == previous['stdout'], 'Memory frontend changed pre-DCE bootstrap state/trace'
report = {'result': 'PRE_DCE_BOOT_MATCHES_BASELINE', 'stdout': result.stdout,
          'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'loweringSha256': hashlib.sha256((output / 'lowering.json').read_bytes()).hexdigest(),
          'wrapperSha256': hashlib.sha256((experiment / 'memory_boot.cpp').read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'baselineBootSha256': hashlib.sha256((base / 'boot.json').read_bytes()).hexdigest(),
          'limits': ['DCE remains closed; exact pre-DCE baseline does not prove cache-enabled whole-bootstrap behavior.',
                     'MemoryContext derives the existing ProcessorContext; backing MMU and CPUContext ABI remain unchanged.']}
(output / 'boot.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS pre-DCE boot: all125 rerouted objects linked; baseline state/trace unchanged; DCE still refused')
