"""Link the existing 125 objects with an isolated original-memcpy harness."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-code-write-observer'
output = private / 'template-copy-native'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
metadata = json.loads((base / 'lowering.json').read_text())
objects = []
for record in metadata['records']:
    source = Path(record['directory']) / record['file']
    obj = Path(str(source) + '.o')
    assert sha(source) == record['sourceSha256'] and sha(obj) == record['objectSha256']
    objects.append(str(obj))
assert len(objects) == 125
(output / 'loader-bat-seed.h').write_bytes((base / 'loader-bat-seed.h').read_bytes())
wrapper = output / 'template-wrapper.cpp'
body = '#include "template_copy_probe.h"\n' + (base / 'boot-wrapper.cpp').read_text()
body = body.replace('int main(int argc, char** argv) {', 'int main(int argc, char** argv) {\n    if (argc == 2 && std::string(argv[1]) == "--template-copy-check") { return experiment_template_copy_probe(); }\n    if (argc == 2 && std::string(argv[1]) == "--template-copy-ni-check") { return experiment_template_copy_probe(true); }')
wrapper.write_text(body)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
exe = output / 'template-copy-probe'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
                         '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(experiment), '-I', str(output), '-I', str(private / 'mass-current'),
                         '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(upstream / 'nWiiAnalyzer/include'),
                         str(wrapper), str(experiment / 'processor_adapter.cpp'), str(upstream / 'nWiiRuntime/src/core/loader.cpp'),
                         *objects, '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
report = {'result': 'ORIGINAL_MEMCPY_HARNESS_LINKED_WITH_EXISTING_FULL_MODULE', 'objects': 125,
          'baseLoweringSha256': sha(base / 'lowering.json'), 'executableSha256': sha(exe),
          'wrapperSha256': sha(wrapper), 'probeSha256': sha(experiment / 'template_copy_probe.h'),
          'scriptSha256': sha(Path(__file__)), 'seedHeaderSha256': sha(output / 'loader-bat-seed.h'),
          'scope': 'Synthetic patched template input fixture; original memcpy unchanged, code-write guard not relaxed.'}
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
print('Linked isolated original-memcpy probe with125existing objects; behavioral comparison pending')
