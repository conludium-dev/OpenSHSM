"""Link existing125objects to the original OS time consumer diagnostic."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
base = Path('work/private-game/static-recomp/mass-timebase')
output = Path('work/private-game/static-recomp/mass-timebase-active')
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
text = (base / 'boot-wrapper.cpp').read_text()
assert text.count('#include "timebase_probe.h"') == 1
text = text.replace('#include "timebase_probe.h"', '#include "timebase_probe.h"\n#include "os_time_probe.h"')
text = text.replace('int main(int argc, char** argv) {', 'int main(int argc, char** argv) {\n    if (argc == 2 && std::string(argv[1]) == "--os-time-check") { return experiment_os_time_probe(); }')
wrapper = output / 'os-time-wrapper.cpp'
wrapper.write_text(text)
exe = output / 'os-time-probe'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
                         '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(experiment), '-I', str(module), '-I', str(upstream / 'nWiiRuntime/include'),
                         '-I', str(upstream / 'nWiiAnalyzer/include'), str(wrapper), str(experiment / 'processor_adapter.cpp'),
                         str(upstream / 'nWiiRuntime/src/core/loader.cpp'), *objects, '-o', str(exe)],
                        capture_output=True, text=True, timeout=180)
(output / 'os-time-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
(output / 'os-time-build.json').write_text(json.dumps({'result': 'COMPILED_NOT_EXECUTION_VERIFIED', 'executableSha256': sha(exe),
                                                      'wrapperSha256': sha(wrapper), 'baseLoweringSha256': sha(base / 'lowering.json'),
                                                      'probeHeaderSha256': sha(experiment / 'os_time_probe.h'), 'scriptSha256': sha(Path(__file__))}, indent=2) + '\n')
