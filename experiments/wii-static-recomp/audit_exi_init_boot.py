"""Retain PI boot checks and validate the EXI initialization advance."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'audit_set_mask_pi.py'
body = builder.read_text().replace('mass-set-mask-pi', 'mass-exi-init-boot')
body = body.replace('set_mask_pi_lowering', 'exi_init_boot_lowering').replace('build_set_mask_pi.py', 'build_exi_init_boot.py')
body = body.replace("lowering['sites'] == 14", "lowering['sites'] == 21")
body = body.replace('calls=167', 'calls=193').replace('167-call', '193-call')
body = body.replace('memory instruction=8020e910 address=cd00680c length=4 read physical=d00680c wimg=5 slot=1',
                    'memory instruction=8020e3c0 address=cd006800 length=4 read physical=d006800 wimg=5 slot=1')
body = body.replace('BOOT_BOUNDARY pc=8020e8f0 lr=802115b0 msr=2030', 'BOOT_BOUNDARY pc=8020e344 lr=8020e344 msr=2030')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
private = Path('work/private-game/static-recomp')
output = private / 'mass-exi-init-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['basePiBuilderSha256'] == sha(experiment / 'build_set_mask_pi.py')
proof_path = private / 'exi-init-backend/comparison.json'
proof = json.loads(proof_path.read_text())
assert proof['verifierSha256'] == sha(experiment / 'verify_exi_init_backend.py')
for name, digest in proof['headerHashes'].items():
    assert digest == sha(experiment / name)
for name, digest in proof['sourceHashes'].items():
    assert digest == sha(Path(name))
assert proof['executableSha256'] == sha(private / 'exi-init-backend/exi-init-probe')
assert proof['generatedHeaderSha256'] == sha(private / 'exi-init-backend/exi-init-generated.h')
assert proof['generatedInputSha256'] == sha(private / 'mass-current/output_62.cpp')
oracle_path = private / 'dolphin-exi-init/comparison.json'
assert proof['oracleSha256'] == sha(oracle_path)
oracle = json.loads(oracle_path.read_text())
inputs = ''.join(f'{row["mode"]} {row["ni"]}\n' for row in oracle['observations'])
native = subprocess.run([str(private / 'exi-init-backend/exi-init-probe')], input=inputs, capture_output=True, text=True, timeout=30)
assert native.returncode == 0 and 'EXI_INIT_GUARDS 16' in native.stdout
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('EXI_INIT_CASE ')]
assert rows == [[row['value'], *row['csrBefore'], *row['controlBefore'], *row['csrAfter'], *row['controlAfter'], row['causeBefore'], row['causeAfter']] for row in oracle['observations']]
boot = json.loads((output / 'boot.json').read_text())
assert boot['exiInitProofSha256'] == sha(proof_path)
assert boot['stdout'].count('EXI_INIT_IDLE_READ_ACCEPTED') == 3
assert boot['stdout'].count('EXI_INIT_CSR_WRITE_ACCEPTED') == 4
path = output / 'audit.json'
report = json.loads(path.read_text())
report['result'] = 'EXI_IDLE_INIT_BOOT_SOURCE_PRIOR_PROOFS_NATIVE32_REPLAY_PASS'
report['basePiAuditorSha256'] = sha(builder)
report['exiInitProofSha256'] = sha(proof_path)
report['nextRead'] = {'instruction': '0x8020e3c0', 'address': '0xcd006800', 'length': 4,
                      'physical': '0x0d006800', 'wimg': 5, 'batSlot': 1}
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS EXIinit32/guards16 and125-object boot; next EXISelect CSR read refused')
