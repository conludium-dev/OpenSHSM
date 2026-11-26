"""Provenance and original-store pre/post observations, not broad decoder acceptance."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import struct
from stock_psq_anomaly import adapt_anomalies
from stock_block_fixture import adapt_block_fixtures
from stock_idct_callbacks import adapt_callbacks

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--fixtures', action='store_true')
parser.add_argument('--callbacks', action='store_true')
args = parser.parse_args()
assert args.tag is None or re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
assert not args.callbacks or args.fixtures
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, guest, full = root / 'window-fp-context', root / 'window-thp-dcbz', root / 'window-quantization'
variant = 'window-idct-fixtures' if args.fixtures else 'window-psq-anomaly'
if args.callbacks:
    variant = 'window-idct-callbacks'
output = root / variant
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
parent = json.loads((base / 'build.json').read_text())
previous = json.loads((guest / 'build.json').read_text())
assert sha(base / 'build.json') == build['baseBuildSha256']
assert sha(guest / 'build.json') == build['guestBuildSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
text, sites = adapt_anomalies((guest / 'output_37.cpp').read_text(), dol_path.read_bytes())
if args.fixtures:
    text = adapt_block_fixtures(text)
if args.callbacks:
    text, callback_sites = adapt_callbacks(text, dol_path.read_bytes())
    assert callback_sites == build['callbackSites']
assert text == (output / 'output_37.cpp').read_text() and sites == build['sites']
assert sha(output / 'output_37.cpp') == build['sourceSha256']
assert sha(output / 'output_37.cpp.o') == build['objectSha256']
assert build['arguments'] == previous['arguments']
for path, digest in previous['retainedObjects'].items():
    assert sha(Path(path)) == digest
assert sha(base / 'libnwiiruntime.a') == build['archiveSha256'] == parent['archiveSha256']
assert sha(full / 'include/runtime/cpu_context.h') == json.loads((full / 'build.json').read_text())['cpuHeaderSha256']
exe_name = 'OpenSHSMStockIDCTFixtures' if args.fixtures else 'OpenSHSMStockPSQAnomaly'
if args.callbacks:
    exe_name = 'OpenSHSMStockIDCTCallbacks'
assert sha(output / exe_name) == build['executableSha256']
command = list(parent['linkCommand'])
command[command.index(str(guest / 'output_37.cpp.o'))] = str(output / 'output_37.cpp.o')
command[command.index('-o') + 1] = str(output / exe_name)
assert command == build['linkCommand']
report = {'result': 'PSQ_ANOMALY_PROVENANCE_PASS', 'sites': len(sites), 'limits': build['limits']}
if args.tag:
    prefix = root / (variant + '-headless-windowed-' + args.tag)
    log_path, run_path = Path(str(prefix) + '.log'), Path(str(prefix) + '-result.json')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
    assert run['originalDolSha256'] == sha(dol_path)
    records = []
    log = log_path.read_text(errors='replace')
    inputs = [(match.start(), int(match[1])) for match in re.finditer(r'\[THPInput\] index=(\d+)', log)]
    reference = (root.parent / 'thp-reference/pubdev-first3.yuvj420p').read_bytes()
    for match in re.finditer(r'\[PSQAnomaly\] ([^\n]+)', log):
        row = dict(re.findall(r'(\w+)=(\S+)', match[1]))
        if not all(key in row for key in ('phase', 'hit', 'pc', 'address', 'reg', 'gqr6', 'value0', 'value1', 'bytes')):
            continue
        row['values'] = [float.fromhex(row['value0']), float.fromhex(row['value1'])]
        row['compressedCaptureIndex'] = next((index for position, index in reversed(inputs) if position < match.start()), None)
        if row['phase'] == 'after' and int(row['gqr6'], 16) == 0x3D043D04 and row['bytes'] != '-':
            expected = []
            for value in row['values']:
                try:
                    single = struct.unpack('f', struct.pack('f', value))[0]
                except OverflowError:
                    single = math.copysign(math.inf, value)
                expected.append(int(max(0, min(255, single / 8))))
            row['expectedBytes'] = bytes(expected).hex()
            row['storeMatchesQuantization'] = row['bytes'] == row['expectedBytes']
            frame = row['compressedCaptureIndex']
            address = int(row['address'], 16)
            for plane, start, width, height, ref_offset, rows in [
                ('Y', 0xE0000000, 640, 480, 0, 16),
                ('U', 0xE0002A00, 320, 240, 307200, 8),
                ('V', 0xE0003480, 320, 240, 384000, 8)]:
                if frame not in (0, 1) or not start <= address < start + width * rows - 1:
                    continue
                plane_path = root / f'{variant}-{args.tag}-thp-frame{frame}-{plane}.bin'
                if not plane_path.exists():
                    continue
                native = plane_path.read_bytes()
                local = address - start
                tile, within = divmod(local, 32)
                x, y = (tile % (width // 8)) * 8 + within % 8, (tile // (width // 8)) * 4 + within // 8
                candidates = []
                for row_start in range(0, height, rows):
                    raw = row_start * width + local
                    actual = native[raw:raw + 2]
                    ref = reference[frame * 460800 + ref_offset + (row_start + y) * width + x:
                        frame * 460800 + ref_offset + (row_start + y) * width + x + 2]
                    if actual == bytes.fromhex(row['bytes']) and any(abs(a - b) > 2 for a, b in zip(actual, ref)):
                        candidates.append({'plane': plane, 'x': x, 'y': row_start + y,
                            'actualBytes': actual.hex(), 'referenceBytes': ref.hex()})
                row['candidateOutputLocations'] = candidates
                break
        records.append(row)
    report.update(returncode=run['terminalReturncode'], deadlineReached=run['deadlineReached'],
        records=records, runSha256=sha(run_path), gpuHangReported='GPU Hang' in log,
        decoderCalls=len(re.findall(r'\[CALL\] 0x80209d80 ', log)))
    report['matchingAfterStores'] = sum(row.get('storeMatchesQuantization', False) for row in records)
    if args.callbacks:
        transitions = []
        for match in re.finditer(r'\[IDCTTransition\] ([^\n]+)', log):
            row = dict(re.findall(r'(\w+)=(\S*)', match[1]))
            if not all(key in row for key in ('phase', 'handled', 'block', 'currentBlock', 'context', 'nextContext', 'fprMask', 'ps1Mask', 'matrixChanged')):
                continue
            transitions.append(row)
        report['transitions'] = transitions
        report['resumeFpDifferences'] = sum(row['phase'] == 'resume' and (int(row['fprMask'], 16) or int(row['ps1Mask'], 16)) != 0 for row in transitions)
        report['sameContextImmediateFpDifferences'] = sum(row['phase'] == 'checkpoint' and row['handled'] == '0'
            and row['context'] == row['nextContext'] and row['pc'] == row['next']
            and (int(row['fprMask'], 16) or int(row['ps1Mask'], 16)) != 0 for row in transitions)
    if args.fixtures:
        report['fixtures'] = {path.name: sha(path) for path in root.glob(f'{variant}-{args.tag}-thp-block*.txt')}
    report['limits'] += ['Candidate output locations use observed MCU row layout and final bytes, not a captured DMA transfer proof.']
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 'records=', len(report.get('records', [])))
for row in report.get('records', [])[:12]:
    print(row['phase'], row['pc'], row['address'], row['values'], row['bytes'], row.get('storeMatchesQuantization'))
