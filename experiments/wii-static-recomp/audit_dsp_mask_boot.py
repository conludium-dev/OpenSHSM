"""Retain original-reset/source checks and replay the DSP-enabled boot profile."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'audit_ipc_reset_fixture.py'
body = builder.read_text().replace('mass-ipc-reset-fixture', 'mass-dsp-mask-boot')
body = body.replace('from ipc_reset_lowering import lower', 'from dsp_mask_boot_lowering import lower')
body = body.replace("'build_ipc_reset_fixture.py'", "'build_dsp_mask_boot.py'")
body = body.replace("'ipc_reset_lowering.py'", "'dsp_mask_boot_lowering.py'")
body = body.replace("lowering['sites'] == 1", "lowering['sites'] == 5")
old = "assert live.returncode == 7 and live.stdout == boot['stdout'] == json.loads((base / 'boot.json').read_text())['stdout']"
assert body.count(old) == 1
body = body.replace(old, "assert live.returncode == 7 and live.stdout == boot['stdout']")
body = body.replace('ORIGINAL_IPC_STORE8_ISOLATED_CASES_MATCH_ORDINARY_BOOT_REFUSAL_UNCHANGED', 'DSP_BOOT_RESET_SOURCE_STALE_PREFIX_REPLAY_PASS')
body = body.replace('Live fixture flag false delegates unchanged refused writer; no IPC reset activation.',
                    'Separate profile accepts verified reset/MI/DSP masks; next hardware access remains refused.')
body = body.replace('PASS originalIPCstore8isolatedcases/38staleentries/pretime; ordinarybootIPCrefusalunchanged',
                    'PASS DSP boot reset8/stale38/pretime/exactreplay')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
private = Path('work/private-game/static-recomp')
output = private / 'mass-dsp-mask-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseFixtureBuilderSha256'] == sha(experiment / 'build_ipc_reset_fixture.py')
for group in ('includedHeaderHashes', 'baseLowererHashes'):
    for name, digest in lowering[group].items():
        assert digest == sha(experiment / name)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
for name, digest in lowering['addedVendorSourceHashes'].items():
    assert digest == sha(upstream / name)
proof_path = private / 'dsp-mask-backend/comparison.json'
proof = json.loads(proof_path.read_text())
assert proof['verifierSha256'] == sha(experiment / 'verify_dsp_mask_backend.py')
assert proof['executableSha256'] == sha(private / 'dsp-mask-backend/dsp-mask-probe')
assert proof['generatedHeaderSha256'] == sha(private / 'dsp-mask-backend/dsp-mask-generated.h')
assert proof['generatedInputSha256'] == sha(private / 'mass-current/output_63.cpp')
assert proof['oracleSha256'] == sha(private / 'dolphin-dsp-mask/comparison.json')
for name, digest in proof['sourceHashes'].items():
    assert digest == sha(Path(name))
boot = json.loads((output / 'boot.json').read_text())
assert boot['dspBackendProofSha256'] == sha(proof_path)
for marker in ('IPC_RESET_BOOT_ACCEPTED', 'MI_MASK_BOOT_ACCEPTED', 'DSP_MASK_BOOT_READ_ACCEPTED', 'DSP_MASK_BOOT_WRITE_ACCEPTED'):
    assert boot['stdout'].count(marker) == 1
assert 'calls=149 reason=' in boot['stdout']
assert 'memory instruction=80217734 address=cd006c00 length=4 read physical=d006c00 wimg=5 slot=1' in boot['stdout']
path = output / 'audit.json'
report = json.loads(path.read_text())
report['baseAuditorSha256'] = sha(builder)
report['dspBackendProofSha256'] = sha(proof_path)
report['nextRead'] = {'instruction': '0x80217734', 'address': '0xcd006c00', 'length': 4, 'physical': '0x0d006c00', 'wimg': 5, 'batSlot': 1}
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS125 source/object hashes; verified DSP mask passes, exact next149-call access retained')
