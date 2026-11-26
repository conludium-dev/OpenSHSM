"""Guard contract, unchanged full-module objects and original accurate-cache OS prefix."""
from pathlib import Path
import base64
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
native = Path('work/private-game/static-recomp/mass-poll')
output = Path('work/private-game/static-recomp/dolphin-poll-probe')
base = Path('work/private-game/static-recomp/mass-branch')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
boot = json.loads((native / 'boot.json').read_text())
assert boot['baseLoweringSha256'] == sha(base / 'lowering.json')
assert boot['adapterSha256'] == sha(experiment / 'boot_poll.h') and boot['scriptSha256'] == sha(experiment / 'build_poll.py')
assert boot['wrapperSha256'] == sha(native / 'boot-wrapper.cpp')
assert boot['baseWrapperSha256'] == sha(Path('work/private-game/static-recomp/mass-l2/boot-wrapper.cpp'))
assert boot['executableSha256'] == sha(native / 'openshsm-mass-boot')
lowering = json.loads((base / 'lowering.json').read_text())
assert len(lowering['records']) == 125
for record in lowering['records']:
    source = Path(record['directory']) / record['file']
    assert record['sourceSha256'] == sha(source) and record['objectSha256'] == sha(Path(str(source) + '.o'))
policy = Path('work/private-game/static-recomp/mass-l2/boot-quarantine.tsv')
assert boot['policySha256'] == sha(policy)
replay = subprocess.run([str(native / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
assert replay.returncode == 7 and replay.stdout == boot['stdout']
assert 'BOOT_POLL checks=26830' in boot['stdout']
comparator = experiment / 'verify_dcache.py'
body = comparator.read_text().split("generation = json.loads((output / 'generation.json').read_text())", 1)[1]
body = "generation = json.loads((output / 'generation.json').read_text())" + body
body = body.replace('build_dcache_probe.py', 'build_poll_probe.py').replace('run_dcache_probe.ps1', 'run_poll_probe.ps1')
body = body.replace('802106c0', '8021c000').replace('802134d8', '8021c054')
body = body.replace('UNVERIFIED_PROCESSOR_REGISTER_1017', 'UNVERIFIED_PROCESSOR_REGISTER_269')
body = body.replace("'DCE_ENABLE_BOOT_PREFIX_VERIFIED'", "'GUARDED_EE0_EARLY_OS_PREFIX_VERIFIED'")
body = body.replace("'0x802106C0 before L2CR read'", "'0x8021C000 before OS timebase read'")
body = body.replace("(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\\n')", '')
body = body.replace("print('PASS scoped native DCE/original accurate-cache boot endpoint; next L2CR1017; 3accepts/8refusals')", '')
exec(compile(body, str(comparator), 'exec'), globals())
assert generation['baseGeneratorSha256'] == sha(experiment / 'build_dcache_probe.py')
assert generation['l2GeneratorSha256'] == sha(experiment / 'build_l2_probe.py')
assert generation['branchGeneratorSha256'] == sha(experiment / 'build_branch_probe.py')
assert struct.unpack_from('>I', data, 24)[0] == 0x80000000
exe = native / 'poll-contract'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(upstream / 'nWiiRuntime/include'),
                         str(experiment / 'poll_contract.cpp'), str(experiment / 'processor_adapter.cpp'), '-o', str(exe)],
                        capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert result.returncode == 0 and 'BOOT_POLL_CONTRACT cleanState 14refusals PASS' in result.stdout
report['contractSourceSha256'] = sha(experiment / 'poll_contract.cpp')
report['contractExeSha256'] = sha(exe)
report['comparisonSourceSha256'] = sha(comparator)
report['guardedPollChecks'] = 26830
report['limits'] = ['Pre-service CPU adapter: EE=0, empty callback queue, no active/pending producer/dispatch/exception states; other states refuse.',
                    'Guarded no-delivery does not implement device ticking, event registration, scheduler delivery/resume or timer progression.',
                    'CPU/FP/stack endpoint comparison does not verify every initialized data/BSS byte or the complete OS initializer.',
                    'Controlled Dolphin accurate-cache fixture; physical Wii/L2/BAT/DMA/locks/quantized paired/OS/IOS/GX/menu/game unverified.']
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS guarded pre-service polling:26830checks/14refusals/original early OS CPU endpoint; next timebase')
