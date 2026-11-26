"""Audit UART integration, the unchanged dispatcher and exact next VI read."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
builder = experiment / 'audit_dispatch_boot.py'
body = builder.read_text().replace('mass-dispatch-boot', 'mass-uart-boot').replace('build_dispatch_boot.py', 'build_uart_boot.py')
old_boundary = 'BOOT_BOUNDARY pc=8020e344 lr=8020e344 msr=2030 calls=286 reason=GetID CSR device or fields unverified'
new_boundary = 'BOOT_BOUNDARY pc=802105d0 lr=802105d0 msr=2030 calls=1942 reason=BAT MMIO/locked-cache/unmapped backing access unavailable; memory instruction=80210620 address=cc00206c length=2 read physical=c00206c wimg=5 slot=1'
body = body.replace(old_boundary, new_boundary)
body = body.replace('PASS existing dispatcher source/whole-call proof/exact286-call replay; device0/1 guard retained',
                    'PASS UART dispatcher source/whole-call proof/exact1942-call replay; VI clock guard retained')
body = body.replace('PASS existing dispatcher/original unmodified module/exact286-call boot guard; no parser repair linked',
                    'PASS UART dispatcher/original module/exact1942-call boot guard; no parser repair linked')
expected_line = "canonical.read_text().replace('        func_80006310(context);', '        run_game(context);')"
assert body.count(expected_line) == 1
body = body.replace(expected_line, expected_line + ".replace('if (++calls > 1000)', 'if (++calls > 20000)')")
marker = "exec(compile(body, str(builder), 'exec'), {'__file__': __file__})"
insert = "body = body.replace('BOOT_GETID_PROFILE phase=2 csr=1008 pi=0', 'BOOT_GETID_PROFILE phase=6 csr=1008 pi=0')\n"
insert += "body = body.replace(\"count('BOOT_TRACE address=8020dca0') == 2\", \"count('BOOT_TRACE address=8020dca0') > 2\")\n"
assert_line = "assert (output / 'boot-wrapper.cpp').read_text()"
cpp_call = '    const int result = original_boot_main(argc, argv);'
wrapper_insert = 'body = body.replace(entry, ' + repr('    nwii::runtime::hw::experimentExiTransfer.uartAllowed = true;\n') + ' + entry)\n'
insert += 'body = body.replace(' + repr(assert_line) + ', ' + repr(wrapper_insert + assert_line) + ')\n'
body = body.replace(marker, insert + marker)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
output = private / 'mass-uart-boot'
boot = json.loads((output / 'boot.json').read_text())
assert boot['functionCallBudget'] == 20000 and boot['backendSha256'] == sha(experiment / 'exi_getid_backend.h')
assert boot['uartProofSha256'] == sha(private / 'uart-native/comparison.json')
proof = json.loads((private / 'uart-native/comparison.json').read_text())
assert proof['verifierSha256'] == sha(experiment / 'verify_uart_native.py')
assert proof['buildSha256'] == sha(private / 'uart-native/build.json')
observer = boot['observer']
assert observer['sites'] == 2
assert observer['inputSha256'] == sha(Path(observer['inputSource']))
assert observer['sourceSha256'] == sha(output / 'output_63.cpp') and observer['objectSha256'] == sha(output / 'output_63.cpp.o')
assert observer['headerSha256'] == sha(experiment / 'uart_next_observer.h')
assert (output / 'output_63.cpp').read_text() == Path(observer['inputSource']).read_text().replace(observer['before'], observer['after'])
assert 'Function-call budget exceeded' not in boot['stdout']
path = output / 'audit.json'
report = json.loads(path.read_text())
report['result'] = 'UART_WHOLE_PROOF_DISPATCH_BOOT_EXACT1942_CALL_REPLAY_VI_READ_REFUSED'
report['baseAuditorSha256'] = sha(builder)
report['uartProofSha256'] = boot['uartProofSha256']
report['next'] = {'instruction': '0x80210620', 'address': '0xcc00206c', 'length': 2, 'physical': '0x0c00206c', 'wimg': 5, 'batSlot': 1,
                  'scope': 'VI clock read during SISetSamplingRate; not enabled and not full controller support.'}
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS UART proof/source/wrapper/exact1942-call replay; next original VI clock read refused')
