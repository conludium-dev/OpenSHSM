"""Pin the actual owned decoder entry capture and retained guest/runtime provenance."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'headless-thp-snapshot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
exe = output / 'OpenSHSMStockTHPSnapshot'
archive = output / 'libnwiiruntime.a'
assert sha(exe) == build['executableSha256'] and sha(archive) == build['archiveSha256']
for member, expected in build['retainedRuntimeMembers'].items():
    assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])).hexdigest() == expected
source = output / 'os_hle_stubs.cpp'
assert sha(source) == build['sourceSha256']
restored = source.read_text().replace('#include "stock_thp_snapshot.h"\n', '', 1).replace(
    '\n    if (function == 0x80209D80) { stock_thp_snapshot::observe(ctx); }', '', 1)
assert restored == (root / 'window-movie-queues/os_hle_stubs.cpp').read_text()
run_path = root / 'headless-sc-pc-headless-decoder-snapshot-retry-result.json'
run = json.loads(run_path.read_text())
assert run['result'] == 'BOUNDED_STOCK_RUN_COMPLETE' and run['thpSnapshot'] and run['thpDump']
assert run['executableSha256'] == sha(exe) and not run['windowed']
log = root / 'headless-sc-pc-headless-decoder-snapshot-retry.log'
assert sha(log) == run['logSha256']
assert log.read_text().count('[THPSnapshot] saved=1') == 1
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
with snapshot.open('rb') as stream:
    header = stream.read(792)
assert header[:8] == b'SHSMFP01'
gpr = struct.unpack_from('<32I', header, 8)
assert struct.unpack_from('<I', header, 728)[0] == 0x80209D80
mem1size = struct.unpack_from('<Q', header, 784)[0]
assert mem1size == 24 * 1024 * 1024 + 8
mem2offset = 792 + mem1size + 8
packet = root / 'headless-sc-pc-decoder-snapshot-retry-thp-packet0.bin'
with snapshot.open('rb') as stream:
    stream.seek(mem2offset + gpr[3] - 0x90000000)
    assert stream.read(packet.stat().st_size) == packet.read_bytes()
component_path = output / 'component-verification.json'
assert json.loads(component_path.read_text())['result'] == 'THP_SNAPSHOT_FORMAT_NONMUTATION_PASS'
(output / 'capture-audit.json').write_text(json.dumps({'result': 'NATIVE_DECODER_ENTRY_SNAPSHOT_CAPTURE_AUDITED',
    'buildSha256': sha(build_path), 'runSha256': sha(run_path), 'logSha256': sha(log),
    'snapshotSha256': sha(snapshot), 'snapshotBytes': snapshot.stat().st_size, 'packetSha256': sha(packet),
    'gpr3To7': list(gpr[3:8]), 'componentVerificationSha256': sha(component_path),
    'auditorSha256': sha(Path(__file__).resolve()),
    'limits': ['One native register/3RAM snapshot; exact observed packet embedded, no device/queue/instructionImages serialization.',
        'Read-only capture changes host I/O timing; not complete Wii save-state, hardware oracle or GUI acceptance.']}, indent=2) + '\n')
print('NATIVE_DECODER_ENTRY_SNAPSHOT_CAPTURE_AUDITED', snapshot.stat().st_size)
