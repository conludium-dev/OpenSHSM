"""Compile original CSR selection block and compare post-init behavior."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_exi_select_dolphin.py')], check=True)
oracle_path = private / 'dolphin-exi-select/comparison.json'
oracle = json.loads(oracle_path.read_text())
output = private / 'exi-select-backend'
output.mkdir(exist_ok=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
source = private / 'mass-current/output_62.cpp'
text = source.read_text()
block = text[text.index('loc_8020E3C0: ;'):text.index('loc_8020E3E4: ;')]
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', original[:256])
markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', block)
assert len(markers) == 9
for address, opcode in markers:
    address = int(address, 16)
    section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    assert struct.unpack_from('>I', original, header[section] + address - header[18 + section])[0] == int(opcode, 16)
block = block.replace('ctx.mmu.read32(', 'nwii::runtime::MMIODispatcher::get().read32(').replace('ctx.mmu.write32(', 'experiment_select_probe_write(')
generated = output / 'exi-select-generated.h'
generated.write_text('inline void experiment_exi_select_block(nwii::runtime::CPUContext& ctx) {\n' + block + '}\n')
exe = output / 'exi-select-probe'
sources = [experiment / 'exi_select_backend_probe.cpp', upstream / 'src/hw/mmio_dispatcher.cpp', upstream / 'src/hw/hw_pi.cpp']
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(output), '-I', str(experiment), '-I', str(upstream / 'include'), *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-3000:]
inputs = ''.join(f'{row["device"]} {row["clock"]} {row["ni"]}\n' for row in oracle['observations'])
expected = [[row['before'], row['value'], row['after'], row['causeBefore'], row['causeAfter']] for row in oracle['observations']]
def run(args):
    result = subprocess.run([str(exe), *args], input=inputs, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and 'EXI_SELECT_GUARDS 7' in result.stdout, result.stderr
    return result, [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('EXI_SELECT_CASE ')]
native, rows = run([])
negative, wrong = run(['--preserve-romdis'])
assert rows == expected and len(rows) == 16
differences = sum(a != b for a, b in zip(wrong, expected))
assert len(wrong) == 16 and differences == 16
(output / 'native.log').write_text(native.stdout + native.stderr)
(output / 'romdis-negative.log').write_text(negative.stdout + negative.stderr)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'GENERATED_EXI_SELECT16_CASES_PASS', 'cases': 16, 'originalWords': 9,
          'statePreservingRefusals': 7, 'preserveRomdisDifferences': differences, 'oracleSha256': sha(oracle_path),
          'generatedInputSha256': sha(source), 'generatedHeaderSha256': sha(generated),
          'headerHashes': {name: sha(experiment / name) for name in ('exi_select_backend.h', 'exi_init_backend.h', 'exi_mask_backend.h')},
          'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Channel0 devices0/1/2, clocks0/1, NI0/1 with explicit post-init3800 seed and existing EXI state.',
                     'CSRbefore/written/readback/PI only; no complete selection eligibility, lock/return, transfers or device-ID protocol.',
                     'No full startup/register/physical Wii equivalence.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS EXISelect9 DOL words/16cases/7refusals/ROMDIS negative16')
