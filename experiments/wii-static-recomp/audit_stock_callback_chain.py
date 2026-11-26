"""Check exact observer provenance and summarize actual wrapper forwarding evidence."""
import argparse
import collections
import hashlib
import json
import re
import subprocess
import struct
from pathlib import Path
from stock_completion_observation import adapt_completion_calls, adapt_completion_pe

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
args = parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-completion-observe'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
for source, name, adapter in (
    (root / 'export/nWiiRuntime/src/core/os_hle_stubs.cpp', 'os_hle_stubs.cpp', adapt_completion_calls),
    (root / 'export/nWiiRuntime/src/hw/hw_pe.cpp', 'hw_pe.cpp', adapt_completion_pe)
):
    assert adapter(source.read_text()) == (output / name).read_text()
assert sha(output / 'ios.cpp') == build['sourceSha256']
assert len(build['retainedObjects']) == 77
assert all(sha(Path(name)) == expected for name, expected in build['retainedObjects'].items())
for member, expected in build['retainedRuntimeMembers'].items():
    for archive in (root / 'window-draw-done/libnwiiruntime.a', output / 'libnwiiruntime.a'):
        data = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
        assert hashlib.sha256(data).hexdigest() == expected
label = 'window-completion-observe-headless-windowed-' + args.tag
run = json.loads((root / (label + '-result.json')).read_text())
assert run['executableSha256'] == sha(output / 'OpenSHSMStockCompletionObserver') == build['executableSha256']
assert run['logSha256'] == sha(root / (label + '.log'))
assert run['originalDolSha256'] == sha(Path('work/private-game/disc/DATA/sys/main.dol'))
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', dol[:256])
original_words = {0x8009B3A8: 0x806DB060, 0x8009B3B0: 0x4818D5A1,
    0x8009B2F4: 0x4818D65D, 0x8009B2F8: 0x906DB060, 0x802AE500: 0x906DCB58,
    0x80228970: 0x93CDC5FC, 0x80216074: 0x480128DD}
for address, expected in original_words.items():
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    assert struct.unpack_from('>I', dol, offset)[0] == expected
log = (root / (label + '.log')).read_text(errors='replace')
pattern = r'\[CompletionCall\] ns=(\d+) fn=([0-9a-f]+) lr=([0-9a-f]+) state= ((?:[0-9a-f]+ ){11}[0-9a-f]+) ring= ((?:[0-9a-f]+ ){5}[0-9a-f]+) watchdog=((?:[0-9a-f]+:){2}[0-9a-f]+)(?: saved80529780=[0-9a-f]+)?(?: module=(?:[0-9a-f]+:){2}[0-9a-f]+)?(?: input=(?:[0-9a-f]{1,2},){32})? pe=((?:[0-9a-f]+:){2}[0-9a-f]+) cp=((?:[0-9a-f]+:){3}[0-9a-f]+)'
rows = sorted(re.findall(pattern, log), key=lambda row: int(row[0]))
assert rows, 'No complete late callback records; forwarding unproven'
counts = collections.Counter(row[1] for row in rows)
forwarded = [row for row in rows if row[1] == '802ad24c' and row[2] == '802ae2b8']
queued = [row for row in rows if int(row[7].split(':')[2], 16) >= 32]
report = {
    'result': 'CALLBACK_OBSERVER_PROVENANCE_PASS', 'completeRecords': len(rows),
    'originalWords': {hex(address): hex(value) for address, value in original_words.items()},
    'counts': dict(counts), 'wrapperForwardedEntryRecords': len(forwarded),
    'queuedRecords': len(queued), 'lastByFunction': {fn: next(row for row in reversed(rows) if row[1] == fn) for fn in counts},
    'firstForwardedEntry': forwarded[0] if forwarded else None,
    'lastForwardedEntry': forwarded[-1] if forwarded else None,
    'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
    'gpuHangReported': 'GPU Hang' in log, 'buildSha256': sha(output / 'build.json'),
    'runSha256': sha(root / (label + '-result.json')),
    'limits': ['Entry records show invocation, not complete execution/return or exact physical Wii behavior.',
        'Missing recorded call alone is not absent callback proof; logging cap and emitter aliases matter.',
        'Observer PASS does not establish menu, rendering, audio, controllers or boot acceptance.']
}
(output / ('audit-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print('PASS callback-observer provenance;', len(rows), 'complete records;', len(forwarded), 'wrapper-forwarded entries; GPU Hang:', report['gpuHangReported'])
