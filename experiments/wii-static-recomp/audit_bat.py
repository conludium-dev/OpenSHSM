"""Audit verified BAT/HID4 scope and retain the unverified next live boundary."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-bat')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_bat.py')], check=True)
live = json.loads((output / 'live-boot.json').read_text())
prior = Path('work/private-game/static-recomp/mass-performance/boot-quarantine.tsv')
removed = '80210840\t//_unhandled\n'
policy = output / 'boot-quarantine.tsv'
assert live['removedPolicyEntry'] == removed and live['basePolicySha256'] == sha(prior)
assert live['policySha256'] == sha(policy)
assert policy.read_text() == ''.join(line for line in prior.read_text().splitlines(True) if line != removed)
assert live['scriptSha256'] == sha(experiment / 'activate_bat.py')
assert live['proofSha256'] == sha(output / 'comparison.json')
exe = output / 'openshsm-mass-boot'
assert live['executableSha256'] == sha(exe)
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'live-replay.log').write_text(replay.stdout + replay.stderr)
assert replay.returncode == 7 and 'BOOT_BOUNDARY pc=802106b0 lr=80210818 msr=2030' in replay.stdout
assert 'BOOT_BOUNDARY pc=802106b0 lr=80210818 msr=2030' in live['stdout']
report = {'result': 'BAT_FRONTEND_HID4_BOUNDED_PASS_NEW_LIVE_ENDPOINT_UNVERIFIED',
          'memoryRoutingLines': 511904, 'registerSites': 162, 'rotateRecordSites': 7198,
          'originalHid4Cases': 8, 'rotateIsaCases': 18816, 'nativeContractGuards': 11,
          'liveNextBoundary': '0x802106B0 HID0 writer value0xC200',
          'comparisonSha256': sha(output / 'comparison.json'), 'liveReportSha256': sha(output / 'live-boot.json'),
          'verifierSha256': sha(Path(__file__)),
          'limits': ['Pre-timebase trace/state matches retained verified baseline; this is not full data/BSS contents or post-timebase boot verification.',
                     'Original HID4/alias/rotate proof accepted only within measured profiles; other BAT/HW function gates retained.',
                     'Next HID0 effects, full live CPU/memory endpoint, physical Wii/protection/page tables/L2-ST0/clock epoch/menu/game pending.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS BAT/HID4 bounded scope; pre-timebase baseline preserved; live nextHID0C200 endpoint still unverified')
