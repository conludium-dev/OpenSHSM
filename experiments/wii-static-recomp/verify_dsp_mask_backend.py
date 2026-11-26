"""Compile the existing generated DSP block and compare original observations."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_dsp_mask_dolphin.py')], check=True)
oracle_path = private / 'dolphin-dsp-mask/comparison.json'
oracle = json.loads(oracle_path.read_text())
output = private / 'dsp-mask-backend'
output.mkdir(exist_ok=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
source = private / 'mass-current/output_63.cpp'
text = source.read_text()
block = text[text.index('loc_802176EC: ;'):text.index('loc_8021772C: ;')]
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', original[:256])
markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', block)
assert len(markers) == 16
for address, opcode in markers:
    address = int(address, 16)
    section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    assert struct.unpack_from('>I', original, header[section] + address - header[18 + section])[0] == int(opcode, 16)
generated = output / 'dsp-mask-generated.h'
block = block.replace('ctx.mmu.read16(', 'nwii::runtime::MMIODispatcher::get().read16(')
block = block.replace('ctx.mmu.write16(', 'nwii::runtime::MMIODispatcher::get().write16(')
generated.write_text('inline void experiment_dsp_mask_block(nwii::runtime::CPUContext& ctx) {\n' + block + '}\n')
exe = output / 'dsp-mask-probe'
sources = [experiment / 'dsp_mask_backend_probe.cpp', upstream / 'src/hw/hw_dsp.cpp',
           upstream / 'src/hw/mmio_dispatcher.cpp', upstream / 'src/hw/hw_pi.cpp', upstream / 'src/core/event_scheduler.cpp']
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(output), '-I', str(upstream / 'include'), *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-3000:]
inputs = ''.join(f'{row["softwareMask"]} {row["ni"]}\n' for row in oracle['observations'])
native = subprocess.run([str(exe)], input=inputs, capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0, native.stderr
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('DSP_MASK_CASE ')]
assert rows == [[row['before'], row['value'], row['after'], row['causeAfter']] for row in oracle['observations']]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'GENERATED_DSP_MASK_BLOCK16_ORIGINAL_CASES_PASS', 'cases': 16, 'originalWords': len(markers),
          'oracleSha256': sha(oracle_path), 'generatedInputSha256': sha(source), 'generatedHeaderSha256': sha(generated),
          'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Generated original block, all8 masks/NI0-NI1, existing vendor DSP on explicit loader0804 seed.',
                     'Compare CSR before/value/after and PI, not complete registers or full preceding boot.',
                     'No pending DSP sources, general audio/DMA/mailbox/IRQ delivery or physical Wii equivalence.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS generated DSP16 original DOL words,16cases/all8 masks with existing vendor backend')
