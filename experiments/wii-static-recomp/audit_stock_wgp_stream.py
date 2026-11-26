"""Correlate accepted/committed/fetched capture layers; never synthesize missing FIFO bytes."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import subprocess
from stock_wgp_stream_patch import adapt

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
args = parser.parse_args()
assert re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, full, output = root / 'window-fp-guard', root / 'window-quantization', root / 'window-wgp-stream'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert sha(base / 'build.json') == build['baseBuildSha256']
assert sha(full / 'build.json') == build['fullBuildSha256']
assert (output / 'gx.cpp').read_text() == adapt((full / 'gx.cpp').read_text())
for path, digest in [(output / 'gx.cpp', build['sourceSha256']), (output / 'gx.cpp.o', build['objectSha256']),
    (output / 'libnwiiruntime.a', build['archiveSha256']), (output / 'OpenSHSMStockWGPStream', build['executableSha256'])]:
    assert sha(path) == digest
for path, digest in build['retainedLinkInputs'].items():
    assert sha(Path(path)) == digest
for member, digest in build['retainedRuntimeMembers'].items():
    for archive in (base / 'libnwiiruntime.a', output / 'libnwiiruntime.a'):
        assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])).hexdigest() == digest
contract = json.loads((output / 'contract.json').read_text())
for path, digest in contract['inputs'].items():
    assert sha(Path(path)) == digest
prefix = root / ('window-wgp-stream-headless-windowed-' + args.tag)
run_path, log_path = Path(str(prefix) + '-result.json'), Path(str(prefix) + '.log')
run = json.loads(run_path.read_text())
assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
assert run['originalDolSha256'] == sha(Path('work/private-game/disc/DATA/sys/main.dol'))
artifact = root / ('window-wgp-stream-' + args.tag)
raw_path = Path(str(artifact) + '-gx-stream.bin')
burst_path = Path(str(artifact) + '-gx-bursts.bin')
cp_path = Path(str(artifact) + '-gx-cp.bin')
segments = Path(str(artifact) + '-gx-segments.txt')
raw, bursts, cp = raw_path.read_bytes(), burst_path.read_bytes(), cp_path.read_bytes()
assert len(bursts) % 36 == 0 and len(cp) % 44 == 0 and raw and cp
committed = b''.join(bursts[i + 4:i + 36] for i in range(0, len(bursts), 36))
fetched = b''.join(cp[i + 12:i + 44] for i in range(0, len(cp), 44))
cp_rows = []
for i in range(0, len(cp), 44):
    address, before, after = struct.unpack_from('>III', cp, i)
    assert after <= before + 32
    cp_rows.append({'address': hex(address), 'before': before, 'after': after, 'consumed': before + 32 - after})
last = cp_rows[-1]
assert last['after'] <= len(fetched)
pending = fetched[-last['after']:] if last['after'] else b''
accepted_tail = raw[len(committed):] if raw.startswith(committed) else None
log = log_path.read_text(errors='replace')
stalls = [{'bytes': int(size), 'head': bytes(int(word, 16) for word in body.split()).hex()}
    for size, body in re.findall(r'\[GX\] stalled remainder (\d+) bytes, head:((?: [0-9a-f]+){1,24})', log)]
stats = [dict(seconds=int(second), frames=int(frames), draws=int(draws))
    for second, frames, draws in re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log)]
records = [line.split() for line in segments.read_text().splitlines()]
assert all(len(row) == 2 for row in records)
cap = len(raw) == 16777216 or len(bursts) // 36 == 524288 or len(cp) // 44 == 524288
report = {'result': 'READ_ONLY_WGP_CAPTURE_AUDIT_PASS', 'runSha256': sha(run_path),
    'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
    'captureHashes': {str(path): sha(path) for path in [raw_path, burst_path, cp_path, segments]},
    'acceptedBytes': len(raw), 'committedBytes': len(committed), 'fetchedBytes': len(fetched),
    'committedEqualsAcceptedPrefix': raw.startswith(committed),
    'acceptedUncommittedTail': accepted_tail.hex() if accepted_tail is not None else None,
    'fetchedEqualsCommitted': fetched == committed, 'lastParserInput': last,
    'pendingSuffix': pending.hex(), 'stalledRecords': stalls, 'stats': stats,
    'lastProducerSegment': records[-1] if records else None, 'captureCapReached': cap,
    'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)),
    'limits': build['limits'] + [
        'Accepted stream includes redirected display-list writes as well as linked writes; equality must be measured, not assumed.',
        'ctx.pc segments may be stale; they are not original store addresses.',
        'Parser before/after byte counts describe actual consumption, not independent command decoding correctness.',
        'Pending suffix and uncommitted tail alone do not establish a boot-blocking command or authorize zero padding.']}
(output / ('audit-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: report[key] for key in ('result', 'acceptedBytes', 'committedBytes', 'fetchedBytes',
    'committedEqualsAcceptedPrefix', 'acceptedUncommittedTail', 'fetchedEqualsCommitted', 'pendingSuffix', 'captureCapReached')}))
