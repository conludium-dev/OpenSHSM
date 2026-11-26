"""Compile and compare whole original SISetXY against the owned-DOL capture."""
from pathlib import Path
import hashlib
import json
import subprocess
import struct

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'si-xy-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_si_xy_dolphin.py')], check=True)
metadata_path = private / 'exi-getid-native/execution.json'
metadata = json.loads(metadata_path.read_text())
for row in metadata['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
record = next(row for row in metadata['records'] if row['file'] == 'output_63.cpp')
source_input = Path(record['source'])
before = '    // 0x8020FEEC: 93E46430\n    nwii::runtime::experiment_getid_write32(ctx, ctx.gpr[4] + 25648, ctx.gpr[31]); // stw r31, 25648(r4)\n'
after = before.replace('experiment_getid_write32(ctx, ctx.gpr[4] + 25648, ctx.gpr[31])', 'experiment_si_xy_write32(ctx, ctx.gpr[4] + 25648, ctx.gpr[31], 0x8020feec)')
assert source_input.read_text().count(before) == 1
source = output / 'output_63.cpp'
source.write_text(source_input.read_text().replace(before, after))
obj = output / 'output_63.cpp.o'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', str(experiment / 'si_xy_frontend.h'),
    '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'loader-bat-seed.h').write_bytes((private / 'exi-getid-native/loader-bat-seed.h').read_bytes())
host = output / 'si-xy-host.cpp'
body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')
host.write_text('#include "si_xy_frontend.h"\n' + body + '\n' + (experiment / 'si_xy_host.cpp').read_text())
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp',
    runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'si-xy-probe'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'),
    '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources),
    *[str(obj) if row['file'] == 'output_63.cpp' else row['object'] for row in metadata['records']], '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout[-1000:] + result.stderr
actual = [[int(value) for value in line.split()[1:]] for line in result.stdout.splitlines() if line.startswith('SI_XY_CASE ')]
oracle_path = private / 'dolphin-si-xy/comparison.json'
oracle = json.loads(oracle_path.read_text())
expected = [[row['index'], row['returnValue'], row['pollRaw'], row['mirrorAfter'], row['msr']] for row in oracle['values']]
assert actual == expected and 'SI_XY_GUARDS 5' in result.stdout
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
section = next(i for i in range(7) if layout[18 + i] <= 0x8020feec < layout[18 + i] + layout[36 + i])
assert struct.unpack_from('>I', dol, layout[section] + 0x8020feec - layout[18 + section])[0] == 0x93e46430
(output / 'comparison.json').write_text(json.dumps({'result': 'COMPILED_WHOLE_SI_SET_XY16_MATCHES_ORIGINAL', 'values': actual, 'guards': 5,
    'builderSha256': sha(Path(__file__)), 'baseExecutionSha256': sha(metadata_path), 'oracleSha256': sha(oracle_path),
    'sourceInput': str(source_input), 'sourceInputSha256': sha(source_input), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'before': before, 'after': after, 'executableSha256': sha(exe), 'sourceHashes': {str(path): sha(path) for path in sources},
    'frontendSha256': sha(experiment / 'si_xy_frontend.h'), 'backendSha256': sha(experiment / 'si_xy_backend.h'),
    'limits': oracle['limits'] + ['Register storage models measured writes only; no active polling/channel producers/timing. Native boot integration still pending.']}, indent=2) + '\n')
print('PASS16 whole compiled original SISetXY matches return/poll/mirror/MSR;5state-preserving refusals;124objects reused')
