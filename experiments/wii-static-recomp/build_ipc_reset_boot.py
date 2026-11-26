"""Advance the separate boot experiment through the verified quiescent IPC reset."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
subprocess.run(['python3', str(experiment / 'verify_ipc_reset_dolphin.py')], check=True)
builder = experiment / 'build_ipc_reset_fixture.py'
body = builder.read_text().replace('mass-ipc-reset-fixture', 'mass-ipc-reset-boot')
body = body.replace('ipc_reset_lowering', 'ipc_reset_boot_lowering')
body = body.replace('ipc_reset_fixture.h', 'ipc_reset_boot.h')
body = body.replace("assert report['sites'] == 1", "assert report['sites'] == 2")
body = body.replace("body = builder.read_text().replace(", "body = builder.read_text().replace(\"'clang++',\", \"'arch', '-arm64', 'clang++',\").replace(")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-ipc-reset-boot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
path = output / 'lowering.json'
report = json.loads(path.read_text())
report['result'] = 'GUARDED_BOOT_IPC_RESET_COMPILED_NEXT_BOUNDARY_UNVERIFIED'
report['baseFixtureBuilderSha256'] = sha(builder)
report['baseFixtureHeaderSha256'] = sha(experiment / 'ipc_reset_fixture.h')
report['baseLowererSha256'] = sha(experiment / 'ipc_reset_lowering.py')
path.write_text(json.dumps(report, indent=2) + '\n')
path = output / 'boot.json'
boot = json.loads(path.read_text())
assert 'IPC_RESET_BOOT_ACCEPTED instruction=802175d4' in boot['stdout']
assert 'memory instruction=802176e4 address=cc00401c value=0 length=2 physical=c00401c wimg=5 slot=1' in boot['stdout']
boot['result'] = 'GUARDED_BOOT_PASSED_ORIGINAL_IPC_RESET_NEXT_BOUNDARY_RETAINED'
boot['loweringSha256'] = sha(output / 'lowering.json')
boot['limits'] = ['One validated quiescent reset store enabled only in this separate profile; ordinary fixture unchanged.',
                  'No general IOS request/IRQ/GPIO/cache/hardware success or full boot acceptance.']
path.write_text(json.dumps(boot, indent=2) + '\n')
