"""Retain the prior boot checks while auditing the verified SI polling store."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'audit_vi_clock_boot.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_si_xy_native.py')], check=True)
builder = experiment / 'audit_vi_clock_boot.py'
body = builder.read_text().replace('mass-vi-clock-boot', 'mass-si-xy-boot').replace('build_vi_clock_boot.py', 'build_si_xy_boot.py')
body = body.replace("sha(experiment / 'vi_clock_frontend.h')", "sha(experiment / 'si_xy_frontend.h')")
registration = '    nwii::runtime::hw::register_vi(nwii::runtime::MMIODispatcher::get());\\n'
assert body.count(registration) == 1
body = body.replace(registration, registration + '    nwii::runtime::hw::experiment_register_si_xy(nwii::runtime::MMIODispatcher::get());\\n')
marker = "assert (output / 'boot-wrapper.cpp').read_text() == expected_wrapper"
assert body.count(marker) == 1
body = body.replace(marker, "expected_wrapper = expected_wrapper.replace('#include \"exi_getid_frontend.h\"', '#include \"si_xy_frontend.h\"')\n" + marker)
before = 'BOOT_BOUNDARY pc=8020fed0 lr=8020fed0 msr=2030 calls=1944 reason=BAT MMIO/locked-cache/unmapped backing access unavailable; memory instruction=8020feec address=cd006430 length=4 write value=1ec0200 physical=d006430 wimg=5 slot=1'
after = 'BOOT_BOUNDARY pc=8020fc94 lr=8020fc94 msr=2030 calls=1946 reason=BAT MMIO/locked-cache/unmapped backing access unavailable'
assert body.count(before) == 1
body = body.replace(before, after)
body = body.replace('PASS existing VI clock callback extension; original NTSC0 sampling arguments;125objects/exact1944-call replay; SI store refused',
    'PASS existing VI/SI polling integration; original NTSC0 sampling arguments;125objects/exact1946-call replay; next SI access refused')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
output = private / 'mass-si-xy-boot'
boot = json.loads((output / 'boot.json').read_text())
si = boot['siXY']
assert si['baseBuilderSha256'] == sha(experiment / 'build_vi_clock_boot.py')
assert si['nativeProofSha256'] == sha(private / 'si-xy-native/comparison.json')
assert si['nativeVerifierSha256'] == sha(private / 'si-xy-native/verification.json')
assert si['backendSha256'] == sha(experiment / 'si_xy_backend.h')
assert si['frontendSha256'] == sha(experiment / 'si_xy_frontend.h')
ghidra_path = private / 'si-xy-native/ghidra/verification.json'
assert si['ghidraSha256'] == sha(ghidra_path)
ghidra = json.loads(ghidra_path.read_text())
assert ghidra['result'] == 'SI_SET_XY_GHIDRA23_INSTRUCTIONS92_BYTES_FULL_BODY'
assert ghidra['runnerSha256'] == sha(experiment / 'verify_si_xy_ghidra.py')
assert ghidra['baseRunnerSha256'] == sha(experiment / 'verify_frsp_roots_ghidra.py')
assert ghidra['scriptSha256'] == sha(experiment / 'ExportFormatSpan.java')
assert ghidra['records'][0]['discoveredBodyBytes'] == 92
for row in ghidra['records']:
    assert row['objectSha256'] == sha(private / 'dtk-output/obj/auto_03_802045CC_text.o')
    assert row['assemblySha256'] == sha(ghidra_path.parent / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(ghidra_path.parent / (row['name'] + '.c'))
path = output / 'audit.json'
report = json.loads(path.read_text())
report['result'] = 'SI_XY_INTEGRATION_EXACT1946_BOOT_REPLAY_NEXT_SI_IDLE_GUARD'
report['siProofSha256'] = si['nativeProofSha256']
report['ghidraSha256'] = si['ghidraSha256']
report['next'] = {'retainedPC': '0x8020fc94', 'sourceInferredInstruction': '0x8020fc98', 'sourceInferredAddress': '0xcd006434',
    'operation': 'read', 'width': 4, 'scope': 'Source inference from current generated SIInit block; no new exact-access observer.'}
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS SI whole-function/Ghidra evidence and exact1946-call boot replay; next SIInit control read remains unsupported')
