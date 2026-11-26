"""Link the existing complete module to a guarded pre-service boot polling contract."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
base = Path('work/private-game/static-recomp/mass-branch')
output = Path('work/private-game/static-recomp/mass-poll')
output.mkdir(exist_ok=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
module = Path('work/private-game/static-recomp/mass-current')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((base / 'lowering.json').read_text())
objects = []
for record in lowering['records']:
    source = Path(record['directory']) / record['file']
    obj = Path(str(source) + '.o')
    assert sha(source) == record['sourceSha256'] and sha(obj) == record['objectSha256']
    objects.append(str(obj))
prior = Path('work/private-game/static-recomp/mass-l2/boot-wrapper.cpp')
old = '    l2_snapshot(context.pc, context);\n    return original_scheduler(context);'
new = '''    try {
        return experiment_boot_poll(context);
    } catch (...) {
        l2_snapshot(context.pc, context);
        throw;
    }'''
text = prior.read_text()
assert text.count(old) == 1
text = text.replace('#include "l2_adapter.h"', '#include "boot_poll.h"').replace(old, new)
text = text.replace('    return original_boot_main(argc, argv);', '''    const int result = original_boot_main(argc, argv);
    std::cout << "BOOT_POLL checks=" << nwii::runtime::bootPollChecks << '\\n';
    return result;''')
wrapper = output / 'boot-wrapper.cpp'
wrapper.write_text(text)
policy = Path('work/private-game/static-recomp/mass-l2/boot-quarantine.tsv')
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
                         '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(experiment), '-I', str(module), '-I', str(upstream / 'nWiiRuntime/include'),
                         '-I', str(upstream / 'nWiiAnalyzer/include'), str(wrapper), str(experiment / 'processor_adapter.cpp'),
                         str(upstream / 'nWiiRuntime/src/core/loader.cpp'), *objects, '-o', str(exe)],
                        capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout
report = {'result': 'GUARDED_POLL_BOOT_ENDPOINT_UNVERIFIED', 'stdout': result.stdout, 'executableSha256': sha(exe),
          'baseLoweringSha256': sha(base / 'lowering.json'), 'wrapperSha256': sha(wrapper),
          'baseWrapperSha256': sha(prior), 'policySha256': sha(policy),
          'adapterSha256': sha(experiment / 'boot_poll.h'), 'scriptSha256': sha(Path(__file__)),
          'scope': 'Pre-service only: no device/event producer is connected; unsupported MMIO/HLE still refuse.'}
(output / 'boot.json').write_text(json.dumps(report, indent=2) + '\n')
print('Reused125objects; guarded polling; next endpoint requires original comparison', flush=True)
print(result.stdout[-2200:], flush=True)
