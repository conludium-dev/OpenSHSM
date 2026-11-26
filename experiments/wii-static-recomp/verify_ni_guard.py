"""Verify measured NI-setter state and pre-effect unsupported-FP refusal policy."""
from pathlib import Path
import hashlib
import json
import subprocess
from ni_guard_lowering import fp_opcode

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'ni-guard'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_frsp_flags.py')], check=True)
proof = json.loads((private / 'dolphin-frsp-flags/comparison.json').read_text())
generation = json.loads((private / 'dolphin-frsp-flags/generation.json').read_text())
inputs, expected = [], []
for record, observation in zip(generation['records'], proof['observations']):
    if record['ni'] == 1:
        before = observation['fpscrBefore'] & ~4
        inputs.append(f'0 {0xffa0004c} {before} {0x2030}\n')
        expected.append([0, observation['fpscrBefore'], 1])
setter_cases = len(inputs)
assert setter_cases == 128
refusals = [(0xffa0004d, 0, 0x2030), (0xffa0008c, 0, 0x2030), (0xffa0004c, 0, 0x30),
            (0xffa0004c, 0, 0x2930), (0xffa0004c, 1, 0x2030), (0xffa0004c, 8, 0x2030),
            (0xffa0004c, 0x800, 0x2030), (0xffa0004c, 0x20000000, 0x2030)]
for opcode, fpscr, msr in refusals:
    inputs.append(f'0 {opcode} {fpscr} {msr}\n')
    expected.append([1, fpscr, int(fp_opcode(opcode))])

opcodes = {int(row.split()[2], 16) for row in (private / 'mass-current/instructions.tsv').read_text().splitlines()}
opcodes |= {primary << 26 | extended << 1 for primary in range(64) for extended in range(1024)}
for opcode in sorted(opcodes):
    for ni in (0, 4):
        supported = opcode == 0xffa0004c or (opcode >> 26 == 63 and (opcode >> 1) & 1023 == 12 and not opcode & 1)
        inputs.append(f'1 {opcode} {ni} {0x2030}\n')
        expected.append([int(bool(ni) and fp_opcode(opcode) and not supported), ni, int(fp_opcode(opcode))])
exe = output / 'ni-guard-probe'
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-I', str(experiment), '-I', str(upstream / 'nWiiRuntime/include'),
                        str(experiment / 'ni_guard_probe.cpp'), '-o', str(exe)], capture_output=True, text=True, timeout=30)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr
result = subprocess.run([str(exe)], input=''.join(inputs), capture_output=True, text=True, timeout=60)
assert result.returncode == 0, result.stderr
assert [list(map(int, row.split())) for row in result.stdout.splitlines()] == expected
report = {'result': 'NI_SETTER_OBSERVED_STATE_AND_STRICT_PRE_EFFECT_GUARD_VERIFIED',
          'originalSetterObservations': setter_cases, 'setterRefusalRollbackCases': len(refusals),
          'policyCases': len(inputs) - setter_cases - len(refusals),
          'adapterSha256': sha(experiment / 'ni_guard.h'), 'probeSha256': sha(experiment / 'ni_guard_probe.cpp'),
          'lowererSha256': sha(experiment / 'ni_guard_lowering.py'), 'verifierSha256': sha(Path(__file__)),
          'originalProofSha256': sha(private / 'dolphin-frsp-flags/comparison.json'),
          'limits': ['Setter FPSCR compared with 128 original NI1 pre-FRSP observations from disclosed fixture.',
                     'Refusal/policy cases are native adapter contracts, not original hardware behavior.',
                     'NI0 retains old behavior; NI1 permits measured setter/non-record FRSP and refuses other FP before effects.',
                     'Full FPU/exception handling, code coverage outside generated IR and native original-function ABI remain unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS NIsetter{setter_cases}observations/{len(refusals)}refusals; guard{report["policyCases"]}policy cases; no runtime activation yet')
