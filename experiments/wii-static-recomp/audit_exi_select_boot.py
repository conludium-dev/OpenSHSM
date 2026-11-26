"""Retain initialization checks and replay the selection-to-transfer boundary."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'audit_exi_init_boot.py'
body = builder.read_text().replace('mass-exi-init-boot', 'mass-exi-select-boot')
body = body.replace('exi_init_boot_lowering', 'exi_select_boot_lowering').replace('build_exi_init_boot.py', 'build_exi_select_boot.py')
body = body.replace("lowering['sites'] == 21", "lowering['sites'] == 23")
body = body.replace('calls=193', 'calls=198').replace('193-call', '198-call')
body = body.replace('memory instruction=8020e3c0 address=cd006800 length=4 read physical=d006800 wimg=5 slot=1',
                    'memory instruction=8020da84 address=cd006810 value=0 length=4 write physical=d006810 wimg=5 slot=1')
body = body.replace('BOOT_BOUNDARY pc=8020e344 lr=8020e344 msr=2030', 'BOOT_BOUNDARY pc=8020da74 lr=8020d8ac msr=2030')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
private = Path('work/private-game/static-recomp')
output = private / 'mass-exi-select-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseInitBuilderSha256'] == sha(experiment / 'build_exi_init_boot.py')
proof_path = private / 'exi-select-backend/comparison.json'
proof = json.loads(proof_path.read_text())
assert proof['verifierSha256'] == sha(experiment / 'verify_exi_select_backend.py')
for name, digest in proof['headerHashes'].items():
    assert digest == sha(experiment / name)
for name, digest in proof['sourceHashes'].items():
    assert digest == sha(Path(name))
assert proof['executableSha256'] == sha(private / 'exi-select-backend/exi-select-probe')
assert proof['generatedHeaderSha256'] == sha(private / 'exi-select-backend/exi-select-generated.h')
assert proof['generatedInputSha256'] == sha(private / 'mass-current/output_62.cpp')
oracle_path = private / 'dolphin-exi-select/comparison.json'
assert proof['oracleSha256'] == sha(oracle_path)
oracle = json.loads(oracle_path.read_text())
inputs = ''.join(f'{row["device"]} {row["clock"]} {row["ni"]}\n' for row in oracle['observations'])
native = subprocess.run([str(private / 'exi-select-backend/exi-select-probe')], input=inputs, capture_output=True, text=True, timeout=30)
assert native.returncode == 0 and 'EXI_SELECT_GUARDS 7' in native.stdout
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('EXI_SELECT_CASE ')]
assert rows == [[row['before'], row['value'], row['after'], row['causeBefore'], row['causeAfter']] for row in oracle['observations']]
boot = json.loads((output / 'boot.json').read_text())
assert boot['exiSelectProofSha256'] == sha(proof_path)
assert boot['stdout'].count('EXI_SELECT_BOOT_READ_ACCEPTED') == 1
assert boot['stdout'].count('EXI_SELECT_BOOT_WRITE_ACCEPTED') == 1
path = output / 'audit.json'
report = json.loads(path.read_text())
report['result'] = 'EXI_SELECT_BOOT_SOURCE_PRIOR_PROOFS_NATIVE16_REPLAY_PASS'
report['baseInitAuditorSha256'] = sha(builder)
report['exiSelectProofSha256'] = sha(proof_path)
report.pop('nextRead', None)
report['nextAccess'] = {'instruction': '0x8020da84', 'address': '0xcd006810', 'value': 0,
                        'length': 4, 'direction': 'write', 'physical': '0x0d006810', 'wimg': 5, 'batSlot': 1}
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS EXIselect16/guards7 and125-object boot; immediate command write refused')
