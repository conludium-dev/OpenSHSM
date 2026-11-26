"""Retain guarded boot checks while validating the existing dispatcher entry."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
builder = experiment / 'audit_exi_getid_boot.py'
body = builder.read_text().replace("output = private / 'mass-exi-getid-boot'", "output = private / 'mass-dispatch-boot'")
body = body.replace('build_exi_getid_boot.py', 'build_dispatch_boot.py')
body = body.replace("assert replay.returncode == boot['returnCode'] == 6", "assert replay.returncode == boot['returnCode'] == 7")
body = body.replace("assert 'BOOT_UNPROVEN_RETURN pc=80199f54' in replay.stderr", "assert 'BOOT_BOUNDARY pc=8020e344 lr=8020e344 msr=2030 calls=286 reason=GetID CSR device or fields unverified' in replay.stdout")
body = body.replace('PASS GetID boot source/whole-call proof/exact replay; unproven return80199F54 retained',
                    'PASS existing dispatcher source/whole-call proof/exact286-call replay; device0/1 guard retained')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
output = private / 'mass-dispatch-boot'
boot = json.loads((output / 'boot.json').read_text())
canonical = experiment / 'mass_boot.cpp'
assert boot['canonicalEntrySha256'] == sha(canonical)
assert boot['entrySourceSha256'] == sha(output / 'mass_boot.cpp')
expected = 'extern "C" void run_game(nwii::runtime::CPUContext&);\n' + canonical.read_text().replace('        func_80006310(context);', '        run_game(context);')
assert (output / 'mass_boot.cpp').read_text() == expected
assert boot['baseBuilderSha256'] == sha(experiment / 'build_exi_getid_boot.py')
assert boot['generatedDispatcherSourceSha256'] == sha(private / 'mass-current/main_output.cpp')
proof = json.loads((private / 'format-parse/comparison.json').read_text())
assert proof['unmodifiedDispatcherCases'] == 126
assert proof['verifierSha256'] == sha(experiment / 'verify_format_parse.py')
assert proof['buildSha256'] == sha(private / 'format-parse/build.json')
path = output / 'audit.json'
report = json.loads(path.read_text())
report['result'] = 'EXISTING_DISPATCHER_BOOT_SOURCE_EXACT_REPLAY_286_CALL_GUARD_PASS'
report['baseAuditorSha256'] = sha(builder)
report['parserDispatcherProofSha256'] = sha(private / 'format-parse/comparison.json')
report['next'] = 'EXISelect0/1/clock4 CSR selection outside measured None0/2 profile; verify MaskROM/UART transaction, do not skip OSReport.'
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS existing dispatcher/original unmodified module/exact286-call boot guard; no parser repair linked')
