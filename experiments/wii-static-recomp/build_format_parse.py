"""Compile one table repair while reusing the existing complete module."""
from pathlib import Path
import hashlib
import json
import subprocess
from format_jump_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'format-parse'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
metadata = json.loads((private / 'exi-getid-native/execution.json').read_text())
record = next(row for row in metadata['records'] if row['file'] == 'output_50.cpp')
input_source = Path(record['source'])
assert sha(input_source) == record['sourceSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
modified, changes = lower(input_source.read_text(), dol)
source = output / 'output_50.cpp'
source.write_text(modified)
obj = output / 'output_50.cpp.o'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', str(experiment / 'exi_getid_frontend.h'),
    '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'loader-bat-seed.h').write_bytes((private / 'exi-getid-native/loader-bat-seed.h').read_bytes())
host = output / 'format-host.cpp'
body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')
body = body.replace('    return experiment_boot_poll(context);', '''    if (context.pc == 0x807f0000) {
        throw std::runtime_error("Format oracle return sentinel");
    }
    return experiment_boot_poll(context);''')
host.write_text(body + '\n' + (experiment / 'format_parse_host.cpp').read_text())
objects = []
for row in metadata['records']:
    assert sha(Path(row['object'])) == row['objectSha256']
    objects.append(str(obj) if row['file'] == 'output_50.cpp' else row['object'])
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp',
    runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'format-probe'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *objects, '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
unfixed = output / 'format-unfixed-probe'
unfixed_command = command.copy()
unfixed_command[unfixed_command.index(str(obj))] = record['object']
unfixed_command[-1] = str(unfixed)
unfixed_result = subprocess.run(unfixed_command, capture_output=True, text=True, timeout=180)
(output / 'unfixed-link.log').write_text(unfixed_result.stdout + unfixed_result.stderr)
assert unfixed_result.returncode == 0, unfixed_result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({'result': 'FORMAT_TABLE_REPAIR_COMPILED_UNVERIFIED', 'changes': changes,
    'builderSha256': sha(Path(__file__)), 'lowererSha256': sha(experiment / 'format_jump_lowering.py'),
    'baseExecutionSha256': sha(private / 'exi-getid-native/execution.json'), 'inputSourceSha256': sha(input_source),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'hostSha256': sha(host), 'executableSha256': sha(exe),
    'hostSourceSha256': sha(experiment / 'format_parse_host.cpp'), 'unfixedExecutableSha256': sha(unfixed),
    'sourceHashes': {str(path): sha(path) for path in sources}}, indent=2) + '\n')
print('Compiled original table56/targets10 repair; execution verification pending')
