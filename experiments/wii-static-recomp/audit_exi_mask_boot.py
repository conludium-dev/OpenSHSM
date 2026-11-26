"""Retain AI boot checks and replay three EXI blocks against retained proof."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'audit_ai_mask_boot.py'
body = builder.read_text().replace('mass-ai-mask-boot', 'mass-exi-mask-boot')
body = body.replace('ai_mask_boot_lowering', 'exi_mask_boot_lowering').replace('build_ai_mask_boot.py', 'build_exi_mask_boot.py')
body = body.replace("lowering['sites'] == 7", "lowering['sites'] == 13")
body = body.replace('calls=150', 'calls=153').replace('next150-call', 'next153-call')
body = body.replace('memory instruction=80217760 address=cd006800 length=4 read physical=d006800 wimg=5 slot=1',
                    'memory instruction=802178a4 address=cc003004 value=f0 length=4 write physical=c003004 wimg=5 slot=1')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
private = Path('work/private-game/static-recomp')
output = private / 'mass-exi-mask-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseAiBuilderSha256'] == sha(experiment / 'build_ai_mask_boot.py')
proof_path = private / 'exi-mask-backend/comparison.json'
proof = json.loads(proof_path.read_text())
assert proof['verifierSha256'] == sha(experiment / 'verify_exi_mask_backend.py')
assert proof['headerSha256'] == sha(experiment / 'exi_mask_backend.h')
assert proof['executableSha256'] == sha(private / 'exi-mask-backend/exi-mask-probe')
assert proof['generatedHeaderSha256'] == sha(private / 'exi-mask-backend/exi-mask-generated.h')
assert proof['generatedInputSha256'] == sha(private / 'mass-current/output_63.cpp')
oracle_path = private / 'dolphin-exi-mask/comparison.json'
assert proof['oracleSha256'] == sha(oracle_path)
for name, digest in proof['sourceHashes'].items():
    assert digest == sha(Path(name))
oracle = json.loads(oracle_path.read_text())
inputs = ''.join(f'{row["channel"]} {row["softwareMask"]} {row["ni"]}\n' for row in oracle['observations'])
native = subprocess.run([str(private / 'exi-mask-backend/exi-mask-probe')], input=inputs, capture_output=True, text=True, timeout=30)
assert native.returncode == 0 and 'EXI_GUARDS 12' in native.stdout
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('EXI_MASK_CASE ')]
assert rows == [[row['before'], row['value'], row['after'], row['causeBefore'], row['causeAfter']] for row in oracle['observations']]
boot = json.loads((output / 'boot.json').read_text())
assert boot['exiBackendProofSha256'] == sha(proof_path)
for channel in range(3):
    for mode in ('READ', 'WRITE'):
        assert boot['stdout'].count(f'EXI_MASK_BOOT_{mode}_ACCEPTED channel={channel}') == 1
path = output / 'audit.json'
report = json.loads(path.read_text())
report['result'] = 'EXI_BOOT_SOURCE_RESET_STALE_PREFIX_PRIOR_PROOFS_NATIVE48_REPLAY_PASS'
report['baseAiAuditorSha256'] = sha(builder)
report['exiBackendProofSha256'] = sha(proof_path)
report.pop('nextRead')
report['nextWrite'] = {'instruction': '0x802178a4', 'address': '0xcc003004', 'value': 0xf0,
                       'length': 4, 'physical': '0x0c003004', 'wimg': 5, 'batSlot': 1}
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS EXI48/guards12 and125-object boot; three channels passed, next PI write refused')
