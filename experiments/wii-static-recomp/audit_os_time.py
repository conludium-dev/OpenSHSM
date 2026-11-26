"""Audit scoped live activation and independent original consumer comparison."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-timebase-active')
base = Path('work/private-game/static-recomp/mass-timebase')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_timebase.py')], check=True)
live = json.loads((output / 'live-boot.json').read_text())
prior = Path('work/private-game/static-recomp/mass-l2/boot-quarantine.tsv')
assert live['basePolicySha256'] == sha(prior)
assert live['removedPolicyEntry'] == '8021C000\tUNVERIFIED_PROCESSOR_REGISTER_269\n'
policy = output / 'boot-quarantine.tsv'
assert policy.read_text() == ''.join(line for line in prior.read_text().splitlines(True) if line != live['removedPolicyEntry'])
assert live['policySha256'] == sha(policy)
assert live['executableSha256'] == sha(base / 'openshsm-mass-boot')
assert live['readerProofSha256'] == sha(base / 'reader-comparison.json')
assert live['scriptSha256'] == sha(experiment / 'activate_timebase.py')
assert 'BOOT_BOUNDARY pc=80210720 lr=802113b0 msr=2030' in live['stdout']
assert 'BOOT_TRACE address=8021c000' in live['stdout'] and 'BOOT_TRACE address=80217520' in live['stdout']
replay = subprocess.run([str(base / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
assert replay.returncode == 7 and 'BOOT_BOUNDARY pc=80210720 lr=802113b0 msr=2030' in replay.stdout
(output / 'live-replay.log').write_text(replay.stdout + replay.stderr)
subprocess.run(['python3', str(experiment / 'verify_os_time_dolphin.py')], check=True)
comparison = json.loads((output / 'os-time-comparison.json').read_text())
assert comparison['result'] == 'ORIGINAL_OS_TIME_DOLPHIN_CONSUMER_MATCH'
report = {'result': 'SCOPED_TIMEBASE_ACTIVE_CONSUMER_VERIFIED_BOOT_ENDPOINT_UNVERIFIED', 'consumerCases': 64,
          'liveNextBoundary': '0x80210720 original mtspr952', 'liveClockEpochAccepted': False,
          'liveReportSha256': sha(output / 'live-boot.json'), 'comparisonSha256': sha(output / 'os-time-comparison.json'),
          'verifierSha256': sha(Path(__file__)),
          'limits': ['Only checked64-bit reader unquarantined; other timer/interrupt/unknown register entries unchanged.',
                     'Dolphin proves the original consumer against observed raw ticks with supplied offsets, not PC live clock epoch/rate synchronization.',
                     'Live post-timebase boot state has not received a complete independent snapshot/memory comparison.',
                     'MMCR/performance counters/RTC/DEC/events/OS/IOS/GX/menu/game acceptance remain pending.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('BOUNDED CONSUMER PASS64cases; scoped live boot advances toSPR952; complete endpoint/epoch still unverified')
