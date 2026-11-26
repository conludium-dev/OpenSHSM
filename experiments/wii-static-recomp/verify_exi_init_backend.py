"""Compile original idle/init slices against an extension of existing EXI state."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_exi_init_dolphin.py')], check=True)
oracle_path = private / 'dolphin-exi-init/comparison.json'
oracle = json.loads(oracle_path.read_text())
output = private / 'exi-init-backend'
output.mkdir(exist_ok=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
source = private / 'mass-current/output_62.cpp'
text = source.read_text()
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', original[:256])
blocks, words = [], 0
for name, start, end, count in [('poll', '8020E910', '8020E940', 12), ('init', '8020E94C', '8020E968', 7)]:
    block = text[text.index(f'loc_{start}: ;'):text.index(f'loc_{end}: ;')]
    markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', block)
    assert len(markers) == count
    for address, opcode in markers:
        address = int(address, 16)
        section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', original, header[section] + address - header[18 + section])[0] == int(opcode, 16)
    words += count
    block = '\n'.join(line for line in block.splitlines() if 'process_pending_callbacks' not in line and 'Spinning at PC' not in line)
    block = block.replace('ctx.mmu.read32(', 'nwii::runtime::MMIODispatcher::get().read32(').replace('ctx.mmu.write32(', 'experiment_init_probe_write(')
    blocks.append(f'inline void experiment_exi_{name}_block(nwii::runtime::CPUContext& ctx) {{\n' + block + '\n}\n')
generated = output / 'exi-init-generated.h'
generated.write_text('\n'.join(blocks))
exe = output / 'exi-init-probe'
sources = [experiment / 'exi_init_backend_probe.cpp', upstream / 'src/hw/mmio_dispatcher.cpp', upstream / 'src/hw/hw_pi.cpp']
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(output), '-I', str(experiment), '-I', str(upstream / 'include'), *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-3000:]
inputs = ''.join(f'{row["mode"]} {row["ni"]}\n' for row in oracle['observations'])
expected = [[row['value'], *row['csrBefore'], *row['controlBefore'], *row['csrAfter'], *row['controlAfter'], row['causeBefore'], row['causeAfter']] for row in oracle['observations']]
def run(args):
    result = subprocess.run([str(exe), *args], input=inputs, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and 'EXI_INIT_GUARDS 16' in result.stdout, result.stderr
    return result, [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('EXI_INIT_CASE ')]
native, rows = run([])
negative, wrong = run(['--drop-init'])
assert rows == expected and len(rows) == 32
differences = sum(a != b for a, b in zip(wrong, expected))
assert len(wrong) == 32 and differences == 31
(output / 'native.log').write_text(native.stdout + native.stderr)
(output / 'drop-init-negative.log').write_text(negative.stdout + negative.stderr)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'GENERATED_EXI_IDLE_INIT32_CASES_PASS', 'cases': 32, 'originalWords': words,
          'statePreservingRefusals': 16, 'dropInitDifferences': differences, 'oracleSha256': sha(oracle_path),
          'generatedInputSha256': sha(source), 'generatedHeaderSha256': sha(generated),
          'headerHashes': {name: sha(experiment / name) for name in ('exi_init_backend.h', 'exi_mask_backend.h')},
          'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Idle controls on existing dispatcher; init writer mutates existing EXI CSR state, no parallel model.',
                     'Native fragment omits generated callback/debug helpers on prepared no-pending idle inputs; no original PPC instructions removed.',
                     'No active/busy transfer, flag acknowledgement/device-ID protocol/full EXIInit/register state or physical Wii proof.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS EXI19 DOL words/32idle-init cases/16refusals/drop-init negative31')
