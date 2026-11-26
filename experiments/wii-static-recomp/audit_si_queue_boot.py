"""Audit current-object startup SI delivery, retained queue evidence and next fallback boundary."""
from pathlib import Path
import hashlib
import json
import re

root = Path('work/private-game/static-recomp')
output = root / 'mass-si-queue-boot'
base = root / 'mass-finite-mem2-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_si_queue_boot.py'))
assert build['queueProofSha256'] == sha(root / 'si-queue-native/comparison.json')
assert build['baseBootSha256'] == sha(base / 'boot.json')
assert build['records'] == json.loads((base / 'boot.json').read_text())['records']
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
for filename in ('mass_boot.cpp', 'boot-quarantine.tsv'):
    assert (output / filename).read_bytes() == (base / filename).read_bytes()
assert (output / 'si_external_delivery.h').read_bytes() == (root / 'si-queue-native/si_external_delivery.h').read_bytes()
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
path = output / 'observed-boot.log'
assert build['logSha256'] == sha(path)
log = path.read_text()
assert 'BOOT_SI_DELIVERY entries=4 callbacks=4' in log
assert 'BOOT_FINITE_MEM2 steps=1765312 returned=1' in log
assert 'BOOT_FLUSH entries=3 phase=0 barriers=3' in log
assert 'BOOT_MI phase=3 writes=3 realEntries=2 active=0 mask=16' in log
assert 'BOOT_DSP commands=17 completed=2 accesses=24' in log
states = [[int(value, 16) for value in line.split()[1:]] for line in log.splitlines() if line.startswith('IRQ_ENABLE_STATE ')]
assert [state[9] for state in states[:5]] == [0, 1, 2, 3, 4]
assert [state[5] for state in states[:5]] == [8, 8, 8, 8, 0]
assert all(state[4] == 0xf8 for state in states)
boundary = next(line for line in log.splitlines() if line.startswith('BOOT_BOUNDARY '))
assert re.fullmatch(r'BOOT_BOUNDARY pc=8021750c lr=80211630 msr=a032 calls=\d+ reason=Interpreter fallback forbidden', boundary)
trace = [line for line in log.splitlines() if line.startswith('BOOT_TRACE ')]
assert trace[-1] == 'BOOT_TRACE address=80213920'
(output / 'audit.json').write_text(json.dumps({'result': 'CURRENT_BOOT_FOUR_SI_IRQ_CALLBACKS_PASS_NEXT_FALLBACK_RETAINED',
    'buildSha256': sha(output / 'build.json'), 'auditorSha256': sha(Path(__file__)), 'boundary': boundary,
    'limits': ['Captured run audit; fresh boot replay still required.',
        'Boundary CPU PC may not identify fallback call site; last trace OSLoadContext80213920 is a locator, not proved fault instruction.',
        'No interpreter permitted or pendingIRQ/context overwritten; no firstframe/menu/audio acceptance.']}, indent=2) + '\n')
print('PASS current125objects:four SI IRQs/callbacks pending8→0; MEM2/flush3 retained; next interpreter refusal unchanged')
