"""Retain DSP boot checks, replay AI advance, validate retained AI binary."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'audit_dsp_mask_boot.py'
body = builder.read_text().replace('mass-dsp-mask-boot', 'mass-ai-mask-boot')
body = body.replace('dsp_mask_boot_lowering', 'ai_mask_boot_lowering').replace('build_dsp_mask_boot.py', 'build_ai_mask_boot.py')
body = body.replace("lowering['sites'] == 5", "lowering['sites'] == 7")
body = body.replace('calls=149', 'calls=150').replace('next149-call', 'next150-call')
body = body.replace('memory instruction=80217734 address=cd006c00 length=4 read physical=d006c00 wimg=5 slot=1',
                    'memory instruction=80217760 address=cd006800 length=4 read physical=d006800 wimg=5 slot=1')
body = body.replace("'0x80217734'", "'0x80217760'").replace("'0xcd006c00'", "'0xcd006800'").replace("'0x0d006c00'", "'0x0d006800'")
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
private = Path('work/private-game/static-recomp')
output = private / 'mass-ai-mask-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseDspBuilderSha256'] == sha(experiment / 'build_dsp_mask_boot.py')
proof_path = private / 'ai-mask-backend/comparison.json'
proof = json.loads(proof_path.read_text())
assert proof['verifierSha256'] == sha(experiment / 'verify_ai_mask_backend.py')
assert proof['headerSha256'] == sha(experiment / 'ai_mask_backend.h')
assert proof['includedVendorSha256'] == sha(Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hw/hw_ai.cpp'))
assert proof['executableSha256'] == sha(private / 'ai-mask-backend/ai-mask-probe')
assert proof['generatedHeaderSha256'] == sha(private / 'ai-mask-backend/ai-mask-generated.h')
assert proof['generatedInputSha256'] == sha(private / 'mass-current/output_63.cpp')
oracle_path = private / 'dolphin-ai-mask/comparison.json'
assert proof['oracleSha256'] == sha(oracle_path)
for name, digest in proof['sourceHashes'].items():
    assert digest == sha(Path(name))
oracle = json.loads(oracle_path.read_text())
inputs = ''.join(f'{row["softwareMask"]} {row["ni"]}\n' for row in oracle['observations'])
native = subprocess.run([str(private / 'ai-mask-backend/ai-mask-probe')], input=inputs, capture_output=True, text=True, timeout=30)
assert native.returncode == 0 and 'AI_GUARDS 4' in native.stdout
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('AI_MASK_CASE ')]
assert rows == [[row['before'], row['value'], row['after'], row['causeAfter']] for row in oracle['observations']]
boot = json.loads((output / 'boot.json').read_text())
assert boot['aiBackendProofSha256'] == sha(proof_path)
for marker in ('AI_MASK_BOOT_READ_ACCEPTED', 'AI_MASK_BOOT_WRITE_ACCEPTED'):
    assert boot['stdout'].count(marker) == 1
path = output / 'audit.json'
report = json.loads(path.read_text())
report['result'] = 'AI_BOOT_SOURCE_RESET_STALE_PREFIX_DSP_AI_PROOFS_REPLAY_PASS'
report['baseDspAuditorSha256'] = sha(builder)
report['aiBackendProofSha256'] = sha(proof_path)
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS retained AI16 cases/refusal4 and125-object boot; next EXI read remains blocked')
