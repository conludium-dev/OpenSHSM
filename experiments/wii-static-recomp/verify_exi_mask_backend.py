"""Compile three generated EXI blocks and compare register/PI causal sequence."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_exi_mask_dolphin.py')], check=True)
oracle_path = private / 'dolphin-exi-mask/comparison.json'
oracle = json.loads(oracle_path.read_text())
output = private / 'exi-mask-backend'
output.mkdir(exist_ok=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
source = private / 'mass-current/output_63.cpp'
text = source.read_text()
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', original[:256])
blocks, words = [], 0
for channel, start, end in [(0, '80217758', '8021779C'), (1, '8021779C', '802177E0'), (2, '802177E0', '80217814')]:
    block = text[text.index(f'loc_{start}: ;'):text.index(f'loc_{end}: ;')]
    markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', block)
    assert len(markers) == (13 if channel == 2 else 17)
    for address, opcode in markers:
        address = int(address, 16)
        section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', original, header[section] + address - header[18 + section])[0] == int(opcode, 16)
    words += len(markers)
    block = block.replace('ctx.mmu.read32(', 'nwii::runtime::MMIODispatcher::get().read32(').replace('ctx.mmu.write32(', 'nwii::runtime::MMIODispatcher::get().write32(')
    blocks.append(f'inline void experiment_exi_mask_block{channel}(nwii::runtime::CPUContext& ctx) {{\n' + block + '}\n')
generated = output / 'exi-mask-generated.h'
generated.write_text('\n'.join(blocks))
exe = output / 'exi-mask-probe'
sources = [experiment / 'exi_mask_backend_probe.cpp', upstream / 'src/hw/mmio_dispatcher.cpp', upstream / 'src/hw/hw_pi.cpp']
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(output), '-I', str(experiment), '-I', str(upstream / 'include'), *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-3000:]
inputs = ''.join(f'{row["channel"]} {row["softwareMask"]} {row["ni"]}\n' for row in oracle['observations'])
expected = [[row['before'], row['value'], row['after'], row['causeBefore'], row['causeAfter']] for row in oracle['observations']]
def run(args):
    result = subprocess.run([str(exe), *args], input=inputs, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and 'EXI_GUARDS 12' in result.stdout, result.stderr
    return result, [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('EXI_MASK_CASE ')]
native, rows = run([])
negative, wrong = run(['--unregistered'])
assert rows == expected and len(rows) == 48
differences = sum(a != b for a, b in zip(wrong, expected))
assert len(wrong) == 48 and differences == 48
(output / 'native.log').write_text(native.stdout + native.stderr)
(output / 'unregistered-negative.log').write_text(negative.stdout + negative.stderr)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'GENERATED_EXI_MASK48_CASES_AND_PI_SEQUENCE_PASS', 'cases': 48, 'originalWords': words,
          'statePreservingRefusals': 12, 'unregisteredDifferences': differences, 'oracleSha256': sha(oracle_path),
          'generatedInputSha256': sha(source), 'generatedHeaderSha256': sha(generated), 'headerSha256': sha(experiment / 'exi_mask_backend.h'),
          'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Three measured loader CSR profiles in existing MMIODispatcher and PI storage; fixed pending/device fields.',
                     'CSR/PI causal sequence matches selected original mask writes; no flag acknowledgement, transfers or device protocol.',
                     'No automatic IRQ/vector delivery, full register/preceding startup or physical Wii proof.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS EXI47 DOL words/48cases/12refusals/negative48 and measured PI transitions')
