"""Replay the MI boot profile and retain existing source and reset checks."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
proof_path = private / 'mi-mask-backend/comparison.json'
proof = json.loads(proof_path.read_text())
assert proof['verifierSha256'] == sha(experiment / 'verify_mi_mask_backend.py')
assert proof['headerSha256'] == sha(experiment / 'mi_mask_backend.h')
assert proof['executableSha256'] == sha(private / 'mi-mask-backend/mi-mask-probe')
for name, digest in proof['sourceHashes'].items():
    assert digest == sha(Path(name))
oracle_path = private / 'dolphin-mi-mask/comparison.json'
assert proof['oracleSha256'] == sha(oracle_path)
oracle = json.loads(oracle_path.read_text())
inputs = ''.join(f'{row["priorSeed"]} {row["requested"]}\n' for row in oracle['observations'])
native = subprocess.run([str(private / 'mi-mask-backend/mi-mask-probe')], input=inputs,
                        capture_output=True, text=True, timeout=30)
assert native.returncode == 0 and 'MI_GUARDS 4' in native.stdout
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('MI_CASE ')]
assert rows == [[row['maskBefore'], row['maskAfter'], row['causeAfter']] for row in oracle['observations']]
builder = experiment / 'audit_ipc_reset_boot.py'
body = builder.read_text().replace('mass-ipc-reset-boot', 'mass-mi-mask-boot')
body = body.replace('ipc_reset_boot_lowering', 'mi_mask_boot_lowering')
body = body.replace('build_ipc_reset_boot.py', 'build_mi_mask_boot.py')
body = body.replace("lowering['sites'] == 2", "lowering['sites'] == 3")
body = body.replace('memory instruction=802176e4 address=cc00401c value=0 length=2 physical=c00401c wimg=5 slot=1',
                    'memory instruction=802176f4 address=cc00500a length=2 read physical=c00500a wimg=5 slot=1')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-mi-mask-boot')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseBootBuilderSha256'] == sha(experiment / 'build_ipc_reset_boot.py')
assert lowering['baseBootLowererSha256'] == sha(experiment / 'ipc_reset_boot_lowering.py')
for name, digest in lowering['includedHeaderHashes'].items():
    assert digest == sha(experiment / name)
boot = json.loads((output / 'boot.json').read_text())
assert boot['miBackendProofSha256'] == sha(Path('work/private-game/static-recomp/mi-mask-backend/comparison.json'))
assert boot['stdout'].count('MI_MASK_BOOT_ACCEPTED instruction=802176e4') == 1
assert 'calls=148 reason=' in boot['stdout']
path = output / 'audit.json'
report = json.loads(path.read_text())
report['result'] = 'MI_MASK_BOOT_SOURCE_RESET_STALE_PREFIX_REPLAY_PASS'
report['baseBootAuditorSha256'] = sha(builder)
report.pop('nextWrite')
report['nextRead'] = {'instruction': '0x802176f4', 'address': '0xcc00500a', 'length': 2,
                      'physical': '0x0c00500a', 'wimg': 5, 'batSlot': 1}
report['limits'][-1] = 'MI zero store accepted only in bounded boot profile; next DSP read still refused.'
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS MI boot125 source/object hashes, reset8, stale38, prefix and exact148-call replay')
