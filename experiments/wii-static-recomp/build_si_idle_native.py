"""Compile the unchanged generated SI idle fragment with guarded MMIO seams."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import struct

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'si-idle-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_si_idle_dolphin.py')], check=True)
metadata_path = private / 'exi-getid-native/execution.json'
metadata = json.loads(metadata_path.read_text())
for row in metadata['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
record = next(row for row in metadata['records'] if row['file'] == 'output_62.cpp')
source_input = Path(record['source'])
text = source_input.read_text()
start, end = text.index('loc_8020FC94: ;'), text.index('loc_8020FCB4: ;')
fragment = text[start:end]
markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', fragment)
assert len(markers) == 8
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
for address, word in markers:
    address = int(address, 16)
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == int(word, 16)
before_read = 'experiment_getid_read32(ctx, ctx.gpr[3] + 25652)'
before_write = 'experiment_getid_write32(ctx, ctx.gpr[3] + 25652, ctx.gpr[0])'
assert fragment.count(before_read) == fragment.count(before_write) == 1
fragment = fragment.replace(before_read, 'experiment_si_idle_read32(ctx, ctx.gpr[3] + 25652, 0x8020fc98)')
fragment = fragment.replace(before_write, 'experiment_si_idle_write32(ctx, ctx.gpr[3] + 25652, ctx.gpr[0], 0x8020fcb0)')
generated = output / 'si-idle-block.h'
generated.write_text('inline void experiment_si_idle_block(nwii::runtime::CPUContext& ctx) {\n' + fragment + '}\n')
(output / 'loader-bat-seed.h').write_bytes((private / 'exi-getid-native/loader-bat-seed.h').read_bytes())
host = output / 'si-idle-host.cpp'
body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')
host.write_text('#include "si_idle_frontend.h"\n' + body + '\n#include "si-idle-block.h"\n' + (experiment / 'si_idle_host.cpp').read_text())
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'si-idle-probe'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in metadata['records']], '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout[-1000:] + result.stderr
actual = [[int(value) for value in line.split()[1:]] for line in result.stdout.splitlines() if line.startswith('SI_IDLE_CASE ')]
oracle_path = private / 'dolphin-si-idle/comparison.json'
oracle = json.loads(oracle_path.read_text())
expected = [[row['index'], row['controlBefore'], row['written'], row['controlAfter'], row['piBefore'], row['piAfter']] for row in oracle['values']]
assert actual == expected and 'SI_IDLE_GUARDS 8' in result.stdout
(output / 'comparison.json').write_text(json.dumps({'result': 'SI_IDLE_FRAGMENT16_MATCHES_ORIGINAL', 'values': actual, 'guards': 8,
    'builderSha256': sha(Path(__file__)), 'baseExecutionSha256': sha(metadata_path), 'oracleSha256': sha(oracle_path),
    'sourceInput': str(source_input), 'sourceInputSha256': sha(source_input), 'generatedSha256': sha(generated),
    'frontendSha256': sha(experiment / 'si_idle_frontend.h'), 'backendSha256': sha(experiment / 'si_idle_backend.h'),
    'executableSha256': sha(exe), 'sourceHashes': {str(path): sha(path) for path in sources}, 'limits': oracle['limits']}, indent=2) + '\n')
print('PASS16 compiled original SI idle fragments/8DOLinstructions/8refusals; no busy/active event-clearing support')
