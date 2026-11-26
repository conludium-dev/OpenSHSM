"""Audit third ACK and actual reply bytes before the unresolved dcbi mapping."""
from pathlib import Path
import base64
import struct
import json

parent = Path('experiments/wii-static-recomp/audit_di_burst_sender_boot.py')
body = parent.read_text().split("assert [line for line in live.splitlines()", 1)[0]
body = body.replace('mass-di-burst-sender-boot', 'mass-di-burst-es-boot').replace(
    'build_di_burst_sender_boot.py', 'build_di_burst_es_boot.py').replace(
    'verify_di_burst_sender_guard.py', 'verify_di_burst_es_guard.py')
exec(compile(body, str(parent), 'exec'), globals())
assert (output / 'di_burst_es.h').read_bytes() == (experiment / 'di_burst_es.h').read_bytes()
assert [line for line in live.splitlines() if line.startswith('DI_BURST_PENDING_ACK ')] == [
    'DI_BURST_PENDING_ACK 135e0080', 'DI_BURST_PENDING_ACK 135e00e0', 'DI_BURST_PENDING_ACK 135e0140']
assert live.count('DI_BURST_86_REPLY\n') == 1 and 'DI_BURST_ES_REPLY' not in live
assert 'BOOT_STM submitted=36 produced=15' in live
assert 'BOOT_BOUNDARY pc=80212fa0 lr=80241d88 msr=30' in live
assert 'reason=No verified BAT mapping; page-table/exception path unavailable' in live
assert 'DI86_SOURCE 2' not in live and 'DI86_SOURCE 3' not in live
assert 'BOOT_STM submitted=30 produced=14' in disabled
assert 'BOOT_BOUNDARY pc=80241c30 lr=80242384 msr=2032' in disabled
assert 'DI_BURST_PENDING_ACK' not in disabled
oracle_path = root / 'dolphin-di-burst-events-disc/fpr-init-true-dolphin.json'
oracle = json.loads(oracle_path.read_text(encoding='utf-8-sig'))
raw = base64.b64decode(oracle['events'])
row = raw[64 + 106 * 1280:64 + 107 * 1280]
for tag, start in [('DI_BURST_REPLY_CACHED', 64), ('DI_BURST_REPLY_PHYSICAL', 128)]:
    line = next(line for line in live.splitlines() if line.startswith(tag + ' '))
    assert bytes(map(int, line.split()[1:])) == row[start:start + 64]
registers = list(map(int, next(line for line in live.splitlines() if line.startswith('BOOT_REGISTERS ')).split()[1:]))
assert registers[3:6] == [0x135e2560, 1, 0] and registers[31] == 0x935e0080
assert '804b2b4c 935e0180' in live
for tag in ('SC_COMPLETE_CONF_PHYSICAL', 'SC_COMPLETE_CONF_CACHED', 'SC_COMPLETE_PRODUCT_PHYSICAL', 'SC_COMPLETE_PRODUCT_CACHED'):
    actual = next(line for line in live.splitlines() if line.startswith(tag + ' '))
    previous_log = (base / 'live-boot.log').read_text()
    expected = next(line for line in previous_log.splitlines() if line.startswith(tag + ' '))
    assert actual == expected
(output / 'es-audit.json').write_text(json.dumps({'result': 'THREE_NATIVE_ACKS_DI86_REPLY64_MATCH_BEFORE_UNMAPPED_DCBI_PASS',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'liveLogSha256': sha(output / 'live-audit.log'), 'disabledLogSha256': sha(output / 'disabled-audit.log'),
    'originalCaptureSha256': sha(oracle_path), 'componentMutantsRejected': 84,
    'limits': ['Both64 native reply views equal original event106; native is stopped BEFORE callback/cache completion.',
        'Full prior SC/product bytes retained; no DI86 callback or ES return proven.',
        'Dolphin current MMU source ignores dcbi page faults; not verified local emulator version or physical Wii behavior.',
        'No cache mapping/no-op/physical pointer retagging added. Exact original cache trace needed next.']}, indent=2) + '\n')
print('PASS fresh thirdACK36/15/native reply64x2 equals original106/fullSC-product/84componentmutants; STOP unmappeddcbi BEFOREcallback/ES')
