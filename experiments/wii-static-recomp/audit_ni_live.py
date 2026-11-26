"""Check scoped NI activation and replay the still-unverified code-write endpoint."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-ni-guard')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'audit_ni_guard.py')], check=True)
live = json.loads((output / 'live-boot.json').read_text())
prior = Path('work/private-game/static-recomp/mass-bat/boot-quarantine.tsv')
policy = output / 'boot-quarantine.tsv'
removed = '80210830\t//_mtfsb1/mtfsb0_stub_(FPSCR_ignored\n'
assert live['removedPolicyEntry'] == removed and prior.read_text().splitlines(True).count(removed) == 1
assert policy.read_text() == prior.read_text().replace(removed, '')
assert live['basePolicySha256'] == sha(prior) and live['policySha256'] == sha(policy)
assert live['proofSha256'] == sha(output / 'audit.json') and live['scriptSha256'] == sha(experiment / 'activate_ni_guard.py')
exe = output / 'openshsm-mass-boot'
assert live['executableSha256'] == sha(exe)
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
(output / 'live-replay.log').write_text(replay.stdout + replay.stderr)
assert replay.returncode == 7 and 'BOOT_TRACE address=80210830' in replay.stdout
assert 'BOOT_BOUNDARY pc=80211940 lr=80211940 msr=2030' in replay.stdout
assert 'Writing translated compiled guest code requires recompilation' in replay.stdout
report = {'result': 'NI_MODE_GUARDED_BOOT_ADVANCE_COMPILED_CODE_WRITE_ENDPOINT_UNVERIFIED',
          'proofSha256': sha(output / 'audit.json'), 'liveSha256': sha(output / 'live-boot.json'),
          'verifierSha256': sha(Path(__file__)), 'endpoint': '0x80211940',
          'limits': ['Only NI setter activated; unverified NI1 FP operations guarded before effects.',
                     'Current stop is immutable-code write, not a proven original Wii fault or accepted complete endpoint.',
                     'Post-clock CPU/memory comparison, mutable exception templates, OS/IOS/GX/menu/game remain pending.']}
(output / 'live-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS scopedNI activation/guards; live advances tocompiled-code-write boundary80211940; full endpoint unverified')
