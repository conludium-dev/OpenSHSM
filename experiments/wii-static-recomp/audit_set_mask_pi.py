"""Replay the final PI boot advance while retaining source/reset/proof checks."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'audit_dsp_mask_boot.py'
body = builder.read_text().replace('mass-dsp-mask-boot', 'mass-set-mask-pi')
body = body.replace('dsp_mask_boot_lowering', 'set_mask_pi_lowering').replace('build_dsp_mask_boot.py', 'build_set_mask_pi.py')
body = body.replace("lowering['sites'] == 5", "lowering['sites'] == 14")
new_branch = '\n    if (argc == 2 && std::string(argv[1]) == "--set-mask-pi-check") { return experiment_set_mask_pi_probe(); }'
insertion = 'body = body.replace("new_main = main + ", ' + repr('new_main = main + ' + repr(new_branch) + ' + ') + ')\n'
old_prefix = '\'#include "ipc_reset_instruction_probe.h"\\n\''
new_prefix = '\'#include "ipc_reset_instruction_probe.h"\\n#include "set_mask_pi_probe.h"\\n\''
insertion += 'body = body.replace(' + repr(old_prefix) + ', ' + repr(new_prefix) + ')\n'
body = body.replace("\nexec(compile(body, str(builder), 'exec'),", "\n" + insertion + "exec(compile(body, str(builder), 'exec'),")
body = body.replace('calls=149', 'calls=167').replace('next149-call', 'next167-call')
body = body.replace('memory instruction=80217734 address=cd006c00 length=4 read physical=d006c00 wimg=5 slot=1',
                    'memory instruction=8020e910 address=cd00680c length=4 read physical=d00680c wimg=5 slot=1')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
private = Path('work/private-game/static-recomp')
output = private / 'mass-set-mask-pi'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['baseDspBuilderSha256'] == sha(experiment / 'build_dsp_mask_boot.py')
for name, script, header in [('ai', 'verify_ai_mask_backend.py', 'ai_mask_backend.h'), ('exi', 'verify_exi_mask_backend.py', 'exi_mask_backend.h')]:
    directory = private / f'{name}-mask-backend'
    proof = json.loads((directory / 'comparison.json').read_text())
    assert proof['verifierSha256'] == sha(experiment / script)
    assert proof['headerSha256'] == sha(experiment / header)
    assert proof['executableSha256'] == sha(directory / f'{name}-mask-probe')
    assert proof['generatedHeaderSha256'] == sha(directory / f'{name}-mask-generated.h')
    assert proof['generatedInputSha256'] == sha(private / 'mass-current/output_63.cpp')
    assert proof['oracleSha256'] == sha(private / f'dolphin-{name}-mask/comparison.json')
    for path, digest in proof['sourceHashes'].items():
        assert digest == sha(Path(path))
pi_oracle_path = private / 'dolphin-pi-mask/comparison.json'
boot = json.loads((output / 'boot.json').read_text())
assert boot['piOracleSha256'] == sha(pi_oracle_path)
assert boot['stdout'].count('PI_FINAL_BOOT_ACCEPTED') == 1
assert 'BOOT_BOUNDARY pc=8020e8f0 lr=802115b0 msr=2030 calls=167' in boot['stdout']
for channel in range(3):
    for mode in ('READ', 'WRITE'):
        assert boot['stdout'].count(f'EXI_MASK_BOOT_{mode}_ACCEPTED channel={channel}') == 1
for marker in ('AI_MASK_BOOT_READ_ACCEPTED', 'AI_MASK_BOOT_WRITE_ACCEPTED'):
    assert boot['stdout'].count(marker) == 1
probe = subprocess.run([str(output / 'openshsm-mass-boot'), '--set-mask-pi-check'], capture_output=True, text=True, timeout=30)
assert probe.returncode == 0 and 'PI_FINAL_GUARDS 9' in probe.stdout
rows = [list(map(int, line.split()[1:])) for line in probe.stdout.splitlines() if line.startswith('PI_FINAL_CASE ')]
assert rows == [[index, 0xf0, 0x10000 if index >= 2 else 0] for index in range(4)]
old = subprocess.run([str(private / 'mass-pi-mask/openshsm-mass-boot'), '--pi-mask-check'], capture_output=True, text=True, timeout=30)
assert old.returncode == 0 and 'PI_MASK_GUARDS 7' in old.stdout
old_rows = [list(map(int, line.split()[1:])) for line in old.stdout.splitlines() if line.startswith('PI_MASK_CASE ')]
oracle = json.loads(pi_oracle_path.read_text())
assert old_rows == [[row['index'], row['requestedMask'], 4 if row['index'] >= 16 else 0, row['causeAfter']] for row in oracle['observations']]
path = output / 'audit.json'
report = json.loads(path.read_text())
report['result'] = 'FINAL_PI_BOOT_SOURCE_RESET_STALE_PREFIX_PRIOR_PROOFS_NATIVE4_GUARDS9_REPLAY_PASS'
report['piOracleSha256'] = sha(pi_oracle_path)
report['piFinalCases'] = 4
report['piFinalStatePreservingRefusals'] = 9
report['baseDspAuditorSha256'] = sha(builder)
report['nextRead'] = {'instruction': '0x8020e910', 'address': '0xcd00680c', 'length': 4,
                      'physical': '0x0d00680c', 'wimg': 5, 'batSlot': 1}
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS finalPI4/guards9, oldPI32/guards7,125objects/reset8/stale38/prefix/exact167-call replay')
