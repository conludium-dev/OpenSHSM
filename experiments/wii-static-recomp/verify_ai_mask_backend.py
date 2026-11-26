"""Compare generated AI block against original captures and detect vendor mismatch."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_ai_mask_dolphin.py')], check=True)
oracle_path = private / 'dolphin-ai-mask/comparison.json'
oracle = json.loads(oracle_path.read_text())
output = private / 'ai-mask-backend'
output.mkdir(exist_ok=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
source = private / 'mass-current/output_63.cpp'
text = source.read_text()
block = text[text.index('loc_8021772C: ;'):text.index('loc_80217758: ;')]
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', original[:256])
markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', block)
assert len(markers) == 11
for address, opcode in markers:
    address = int(address, 16)
    section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    assert struct.unpack_from('>I', original, header[section] + address - header[18 + section])[0] == int(opcode, 16)
block = block.replace('ctx.mmu.read32(', 'experiment_ai_probe_read(').replace('ctx.mmu.write32(', 'experiment_ai_probe_write(')
generated = output / 'ai-mask-generated.h'
generated.write_text('static uint32_t experiment_ai_probe_read(uint32_t);\nstatic void experiment_ai_probe_write(uint32_t, uint32_t);\ninline void experiment_ai_mask_block(nwii::runtime::CPUContext& ctx) {\n' + block + '}\n')
exe = output / 'ai-mask-probe'
sources = [experiment / 'ai_mask_backend_probe.cpp', experiment / 'ai_mask_backend.cpp', upstream / 'src/hw/mmio_dispatcher.cpp', upstream / 'src/hw/hw_pi.cpp']
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(output), '-I', str(experiment), '-I', str(upstream / 'include'), '-I', str(upstream / 'src/hw'), *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-3000:]
inputs = ''.join(f'{row["softwareMask"]} {row["ni"]}\n' for row in oracle['observations'])
expected = [[row['before'], row['value'], row['after'], row['causeAfter']] for row in oracle['observations']]
def run(args):
    result = subprocess.run([str(exe), *args], input=inputs, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and 'AI_GUARDS 4' in result.stdout, result.stderr
    return result, [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith('AI_MASK_CASE ')]
native, rows = run([])
negative, wrong = run(['--vendor'])
assert rows == expected and len(rows) == 16
differences = sum(a != b for a, b in zip(wrong, expected))
assert len(wrong) == 16 and differences == 15
(output / 'native.log').write_text(native.stdout + native.stderr)
(output / 'vendor-negative.log').write_text(negative.stdout + negative.stderr)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'GENERATED_WII_AI_MASK16_CASES_PASS_VENDOR15_MISMATCHES', 'cases': 16, 'originalWords': 11,
          'statePreservingRefusals': 4, 'vendorDifferences': differences,
          'oracleSha256': sha(oracle_path), 'generatedInputSha256': sha(source), 'generatedHeaderSha256': sha(generated),
          'headerSha256': sha(experiment / 'ai_mask_backend.h'), 'includedVendorSha256': sha(upstream / 'src/hw/hw_ai.cpp'),
          'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Explicit loader42 seed and bounded Wii mask write use existing vendor ai_cr storage/dispatcher.',
                     'CD006C00 alias and corrected quiescent mask semantics are native adapters, not general AI.',
                     'No playback/sample-rate/timing/pending interrupts/full registers or physical Wii proof.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS AI11 DOLwords/16original cases/4refusals; uncorrected vendor15mismatches')
