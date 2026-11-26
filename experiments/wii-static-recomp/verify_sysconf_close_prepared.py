"""Compare native prepared CLOSE packet/work/control with the original first file CLOSE."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'mass-sysconf-close-observer'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = json.loads((output / 'observation.json').read_text())
build = json.loads((root / 'mass-sysconf-read-boot/build.json').read_text())
assert report['builderSha256'] == sha(experiment / 'observe_sysconf_close_native.py')
assert report['records'] == build['records']
for path, digest in {**report['sourceHashes'], **report['headerHashes']}.items():
    assert sha(Path(path)) == digest
for row in report['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name, digest in build['headerHashes'].items():
    assert sha(output / Path(name).name) == digest
capture_path = root / 'dolphin-sysconf-events-fixed-disc/fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
raw = base64.b64decode(capture['events'])
event = raw[64 + 66 * 1280:64 + 67 * 1280]
lines = (output / 'observation.log').read_text().splitlines()


def check(rows):
    def values(prefix):
        matches = [row[len(prefix) + 1:].split() for row in rows if row.startswith(prefix + ' ')]
        assert len(matches) == 1
        return matches[0]

    assert values('SC_CLOSE_ARGUMENTS') == ['8053fc98', '935e00a0', '1', '80240680', '0']
    for view, offset in (('CACHED', 64), ('PHYSICAL', 128)):
        expected = bytearray(event[offset:offset + 64])
        struct.pack_into('>I', expected, 24, 0x80540010)
        assert bytes(map(int, values('SC_CLOSE_PACKET_' + view))) == expected
    assert bytes(map(int, values('SC_CLOSE_WORK_CACHED'))) == event[320:640]
    assert bytes(map(int, values('SC_CLOSE_CONTROL_CACHED'))) == event[640:1040]
    assert 'BOOT_STM submitted=20 produced=9' in rows
    assert 'BOOT_STM_ASYNC dispatched=1 pending=1 6 1 324927520 4096 4796512 32 4796544 32' in rows


check(lines)
mutants = 0
for prefix in ('SC_CLOSE_ARGUMENTS', 'SC_CLOSE_PACKET_CACHED', 'SC_CLOSE_PACKET_PHYSICAL',
    'SC_CLOSE_WORK_CACHED', 'SC_CLOSE_CONTROL_CACHED', 'BOOT_STM submitted=', 'BOOT_STM_ASYNC dispatched='):
    try:
        check([line for line in lines if not line.startswith(prefix)])
    except AssertionError:
        mutants += 1
    else:
        raise AssertionError(prefix)
(output / 'verification.json').write_text(json.dumps({'verifierSha256': sha(Path(__file__)),
    'observationSha256': sha(output / 'observation.json'), 'oracleSha256': sha(capture_path),
    'result': 'PREPARED_CLOSE_PACKET64_WORK320_CONTROL400_ORIGINAL_EVENT66_EQUAL', 'mutants': mutants,
    'limits': ['Ignored virtual pointer53ff90→540010 relocation; prepared CLOSE only, not completion.']}, indent=2) + '\n')
print('PASS prepared CLOSE/both64/work320/control400 originalevent66;125 objects unchanged;7mutants')
