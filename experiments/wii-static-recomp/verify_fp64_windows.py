"""Execute the same raw-bit transfer oracle and refusal contracts on Windows x86-64."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-fp64')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
oracle = json.loads((output / 'comparison.json').read_text())
assert oracle['adapterSha256'] == sha(experiment / 'fp64_transfer.h')
assert oracle['probeSha256'] == sha(experiment / 'fp64_probe.cpp')
assert oracle['contractSha256'] == sha(experiment / 'fp64_contract.cpp')
zig = 'C:/OpenSHSM-lab/work/research/zig/zig-x86_64-windows-0.14.1/zig.exe'
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
executables = []
for name in ('probe', 'contract'):
    exe = output / f'fp64-{name}-windows.exe'
    command = [zig, 'c++', '-std=c++20', '-O2', '-target', 'x86_64-windows-gnu', '-I', str(experiment),
               '-I', 'work/private-game/static-recomp/mass-ni-guard', '-I', str(upstream / 'nWiiRuntime/include'),
               str(experiment / f'fp64_{name}.cpp'), '-o', str(exe)]
    build = subprocess.run(command, capture_output=True, text=True, timeout=300)
    (output / f'windows-{name}-build.log').write_text(build.stdout + build.stderr)
    assert build.returncode == 0, build.stderr[-3000:]
    executables.append(exe)
inputs = []
for row in generation['records']:
    inputs.append(f"{row['bits']} {row['ps1']} {row['ni'] * 4} {row['loadOpcode']} {row['storeOpcode']} {row['inputAddress'] & 7}\n")
result = subprocess.run([str(executables[0])], input=''.join(inputs), capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
expected = [[row['ps0'], row['ps1'], row['fpscr'], row['stored'], row['loadRaDelta'], row['storeRaDelta']] for row in oracle['observations']]
assert [list(map(int, line.split())) for line in result.stdout.splitlines()] == expected
contract = subprocess.run([str(executables[1])], capture_output=True, text=True, timeout=30)
assert contract.returncode == 0 and contract.stdout == 'FP64_CONTRACT guards=9 zero_RA=3\n', contract
report = {'result': 'WINDOWS_X64_FP64_ORIGINAL_ORACLE_AND_CONTRACT_MATCH', 'cases': 320,
          'refusalRollbackCases': 9, 'zeroRaContracts': 3, 'oracleSha256': sha(output / 'comparison.json'),
          'adapterSha256': sha(experiment / 'fp64_transfer.h'), 'scriptSha256': sha(Path(__file__)),
          'executableSha256': [sha(path) for path in executables],
          'limits': ['Standalone Windows FP64 helper, not full125-object Windows recomp or SDL gameplay acceptance.']}
(output / 'windows-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS Windowsx64 FP64320originalobservations/9refusals/3zeroRAcontracts; fullWindowsmodule pending')
