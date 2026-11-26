"""Compare the bounded MI region to retained original-store observations."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_mi_mask_dolphin.py')], check=True)
oracle_path = private / 'dolphin-mi-mask/comparison.json'
oracle = json.loads(oracle_path.read_text())
output = private / 'mi-mask-backend'
output.mkdir(exist_ok=True)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
exe = output / 'mi-mask-probe'
sources = [experiment / 'mi_mask_backend_probe.cpp', upstream / 'src/hw/mmio_dispatcher.cpp', upstream / 'src/hw/hw_pi.cpp']
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-I', str(experiment), '-I', str(upstream / 'include'), *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-2000:]
inputs = ''.join(f'{row["priorSeed"]} {row["requested"]}\n' for row in oracle['observations'])
native = subprocess.run([str(exe)], input=inputs, capture_output=True, text=True, timeout=30)
assert native.returncode == 0 and 'MI_GUARDS 4' in native.stdout
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('MI_CASE ')]
expected = [[row['maskBefore'], row['maskAfter'], row['causeAfter']] for row in oracle['observations']]
assert rows == expected and len(rows) == 32
zero_cause = subprocess.run([str(exe), '--pi-zero'], input=inputs, capture_output=True, text=True, timeout=30)
assert zero_cause.returncode == 0
zero_rows = [list(map(int, line.split()[1:])) for line in zero_cause.stdout.splitlines() if line.startswith('MI_CASE ')]
assert zero_rows == [row[:2] + [0] for row in expected]
negative = subprocess.run([str(exe), '--unregistered'], input=inputs, capture_output=True, text=True, timeout=30)
assert negative.returncode == 0
negative_rows = [list(map(int, line.split()[1:])) for line in negative.stdout.splitlines() if line.startswith('MI_CASE ')]
differences = sum(a != b for a, b in zip(negative_rows, expected))
assert len(negative_rows) == 32 and differences == 30
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'BOUNDED_MI_MASK32_ORIGINAL_CASES_PASS', 'cases': 32, 'statePreservingRefusals': 4, 'unregisteredDifferences': differences,
          'nativeZeroCauseCases': 32,
          'oracleSha256': sha(oracle_path), 'headerSha256': sha(experiment / 'mi_mask_backend.h'), 'sourceHashes': {str(path): sha(path) for path in sources},
          'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['One16-bit MI mask region on existing MMIODispatcher; no pending protection faults or IRQ production.', 'Extra PI0 cases test native boot adaptation only; original observations have PI10000.', 'No full MI hardware, 32-bit/unaligned access, timing or physical Wii equivalence claim.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS MI32 observations/refusal4/unregistered-negative30; no full MI/IRQ activation')
