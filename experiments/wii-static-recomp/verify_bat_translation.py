"""Compare isolated BAT resolution to observed HID4 alias effects and explicit boundary cases."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-hid4-probe')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_hid4_dolphin.py')], check=True)
proof_path = output / 'comparison.json'
proof = json.loads(proof_path.read_text())
exe = output / 'bat-probe'
result = subprocess.run(['clang++', '-std=c++20', '-O2', '-I', str(experiment), str(experiment / 'bat_probe.cpp'), '-o', str(exe)],
                        capture_output=True, text=True, timeout=30)
(output / 'bat-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
inputs, expected = [], []
for observation in proof['observations']:
    bank = [[0, 0] for _ in range(8)]
    bank[3], bank[4] = observation['dbat3'], observation['dbat4']
    inputs.append([observation['hid4'], observation['msr'], 0xa0000000, 0, *[value for pair in bank for value in pair]])
    physical, slot = (0x720000, 4) if observation['hid4'] & 0x02000000 else (0x700000, 3)
    expected.append(f'{physical} 4 {slot}')
    assert observation['aliasValue'] == {0x700000: 0x11223344, 0x720000: 0x55667788}[physical]
synthetic_cases = 0
for blocks in [0, 1, 3, 7, 15, 31, 63, 127, 255, 511, 1023, 2047]:
    size = (blocks + 1) * 0x20000
    for slot in range(8):
        for offset in [0, 1, 3, 31, 0x1ffff, size - 1]:
            bank = [[0, 0] for _ in range(8)]
            bank[slot] = [0x80000002 | (blocks << 2), 0x10000002]
            for instruction in (0, 1):
                inputs.append([0x02000000, 0x30, 0x80000000 + offset, instruction, *[value for pair in bank for value in pair]])
                expected.append(f'{0x10000000 + offset} 0 {slot}')
                synthetic_cases += 1
guards = []
bank = [[0, 0] for _ in range(8)]
bank[4] = [0xa0000002, 0x00720022]
guards.append([0, 0x30, 0xa0000000, 0, *[value for pair in bank for value in pair]])
guards.append([0x02000000, 0x4030, 0xa0000000, 0, *[value for pair in bank for value in pair]])
for pair in [[0xa000000a, 0x00720022], [0xa0000006, 0x00720022], [0xa0020006, 0x00700022], [0xa0000002, 0x00720021]]:
    bank = [[0, 0] for _ in range(8)]
    bank[0] = pair
    guards.append([0x02000000, 0x30, 0xa0000000, 0, *[value for pair in bank for value in pair]])
inputs.extend(guards)
expected.extend(['REFUSED'] * len(guards))
result = subprocess.run([str(exe)], input=''.join(' '.join(map(str, row)) + '\n' for row in inputs), capture_output=True, text=True, timeout=30)
(output / 'bat-native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0
actual = result.stdout.splitlines()
assert actual == expected, [(index, a, b) for index, (a, b) in enumerate(zip(actual, expected)) if a != b][:8]
report = {'result': 'ISOLATED_BAT_REFERENCE_ALIAS_MATCH_NOT_RUNTIME_INTEGRATED', 'dolphinAliasCases': 8,
          'syntheticBoundaryCases': synthetic_cases, 'refusalCases': len(guards),
          'originalProofSha256': sha(proof_path), 'headerSha256': sha(experiment / 'bat_translation.h'),
          'probeSha256': sha(experiment / 'bat_probe.cpp'), 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Eight observed Dolphin alias reads support SBE/slot selection; synthetic boundary cases are algebraic tests, not an original execution oracle.',
                     'Reference overlap priority follows Dolphin; physical overlapping BAT behavior unverified.',
                     'Supervisor RW/aligned valid masks only; page tables, user protection and exception delivery unsupported.',
                     'Pure resolver is not wired into existing CPUContext/MMU/cache; original HID4 native function and live boot remain quarantined.']}
(output / 'bat-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS isolatedBAT:8Dolphin alias observations/{synthetic_cases}synthetic boundary cases/{len(guards)}refusals; runtime unchanged')
