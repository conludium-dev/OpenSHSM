"""Reuse original-store and stale-entry checks, then replay the scoped boot advance."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'audit_ipc_reset_fixture.py'
body = builder.read_text().replace('mass-ipc-reset-fixture', 'mass-ipc-reset-boot')
body = body.replace('from ipc_reset_lowering import lower', 'from ipc_reset_boot_lowering import lower')
body = body.replace("'build_ipc_reset_fixture.py'", "'build_ipc_reset_boot.py'")
body = body.replace("'ipc_reset_lowering.py'", "'ipc_reset_boot_lowering.py'")
body = body.replace("lowering['sites'] == 1", "lowering['sites'] == 2")
old = "assert live.returncode == 7 and live.stdout == boot['stdout'] == json.loads((base / 'boot.json').read_text())['stdout']"
assert body.count(old) == 1
body = body.replace(old, "assert live.returncode == 7 and live.stdout == boot['stdout']\nassert live.stdout.count('IPC_RESET_BOOT_ACCEPTED instruction=802175d4') == 1\nassert 'BOOT_BOUNDARY pc=80217650 lr=80217608 msr=2030' in live.stdout")
body = body.replace('ORIGINAL_IPC_STORE8_ISOLATED_CASES_MATCH_ORDINARY_BOOT_REFUSAL_UNCHANGED',
                    'ORIGINAL_IPC_STORE8_AND_SCOPED_BOOT_RESET_NEXT_GUARD_REPLAY_PASS')
body = body.replace('Live fixture flag false delegates unchanged refused writer; no IPC reset activation.',
                    'Only the validated quiescent reset advances in this separate boot profile; next hardware boundary remains guarded.')
body = body.replace('PASS originalIPCstore8isolatedcases/38staleentries/pretime; ordinarybootIPCrefusalunchanged',
                    'PASS originalIPCstore8/stale38/pretime/scopedboot reset accepted once, next boundary retained')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-ipc-reset-boot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseFixtureBuilderSha256'] == sha(experiment / 'build_ipc_reset_fixture.py')
assert lowering['baseFixtureHeaderSha256'] == sha(experiment / 'ipc_reset_fixture.h')
assert lowering['baseLowererSha256'] == sha(experiment / 'ipc_reset_lowering.py')
path = output / 'audit.json'
report = json.loads(path.read_text())
report['baseAuditorSha256'] = sha(builder)
assert 'memory instruction=802176e4 address=cc00401c value=0 length=2 physical=c00401c wimg=5 slot=1' in json.loads((output / 'boot.json').read_text())['stdout']
report['nextWrite'] = {'instruction': '0x802176e4', 'address': '0xcc00401c', 'value': 0, 'length': 2, 'physical': '0x0c00401c', 'wimg': 5, 'batSlot': 1}
report['limits'].append('Exact next MI mask write observed and still refused; no MI/SetInterruptMask/full interrupt initialization acceptance.')
path.write_text(json.dumps(report, indent=2) + '\n')
