"""Verify exact original-wrapper restoration, retained runtime and scoped oracle results."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
from stock_scan_restore import restore_guest, restore_dispatch

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--continuation-routes', action='store_true')
args = parser.parse_args()
assert args.tag is None or re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
full, base = root / 'window-quantization', root / 'window-fp-guard'
variant = 'window-scan-routes' if args.continuation_routes else 'window-scan-restore'
output = root / variant
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert sha(base / 'build.json') == build['baseBuildSha256']
assert sha(full / 'build.json') == build['fullBuildSha256']
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
mass = root.parent / 'mass-current/output_51.cpp'
assert sha(mass) == build['massSourceSha256']
tables = json.loads((root / 'fp-guard-component/report.json').read_text())['tables']
expected, words = restore_guest((base / 'output_31.cpp').read_text(), mass.read_text(), dol.read_bytes(), tables)
assert (output / 'output_31.cpp').read_text() == expected and words == build['originalWords']
assert (output / 'main_output.cpp').read_text() == restore_dispatch((full / 'main_output.cpp').read_text(), args.continuation_routes)
for item in build['compiled']:
    assert sha(output / item['source']) == item['sourceSha256']
    assert sha(output / (item['source'] + '.o')) == item['objectSha256']
    assert sha(Path(item['originalPath'])) == item['originalSha256']
for path, digest in build['retainedInputs'].items():
    assert sha(Path(path)) == digest
assert sha(output / ('OpenSHSMStockScanRoutes' if args.continuation_routes else 'OpenSHSMStockScanRestore')) == build['executableSha256']
proof = json.loads((output / 'original-compare.json').read_text())
assert proof['result'] == 'RESTORED_SCAN_INTEGER_PPC_PASS_FLOAT_ORACLE_UNAVAILABLE'
assert proof['scriptSha256'] == sha(Path('experiments/wii-static-recomp/verify_stock_scan_original.py'))
assert proof['probeBuildSha256'] == sha(output / 'probe-build.json')
assert proof['nativeLogSha256'] == sha(output / 'original-compare-native.log')
probe = json.loads((output / 'probe-build.json').read_text())
assert probe['parentBuildSha256'] == sha(output / 'build.json')
assert probe['sourceSha256'] == sha(Path('experiments/wii-static-recomp/stock_scan_probe.cpp'))
assert probe['objectSha256'] == sha(output / 'scan-probe.cpp.o')
assert probe['executableSha256'] == sha(output / 'scan-probe')
assert probe['dispatcherSourceSha256'] == sha(output / 'probe-dispatcher.cpp')
assert probe['dispatcherObjectSha256'] == sha(output / 'probe-dispatcher.cpp.o')
for path, digest in probe['linkInputs'].items():
    assert sha(Path(path)) == digest
verified = [row for row in proof['cases'] if row['passed'] is not None]
assert len(verified) == 15 and all(row['passed'] for row in verified)
assert len(proof['cases']) == 20 and all(row.get('nativeLogicalFixturePassed') for row in proof['cases'][15:])
report = {'result': 'ORIGINAL_SCAN_RESTORATION_AUDIT_PASS_WITH_FLOAT_ORACLE_LIMIT', 'originalWords': 76,
    'integerOriginalCases': 15, 'nativeFloatCases': 5, 'limitations': build['limits'] + proof['limits']}
dispatcher = (output / 'main_output.cpp').read_text()
bounds_text = dispatcher.split('static void dispatch_hle_', 1)[0]
overlaps = [(int(start, 16), int(end, 16), function) for start, end, function in
    re.findall(r'\{0x([0-9A-F]+), 0x([0-9A-F]+), (\w+)\}', bounds_text)
    if int(start, 16) <= 0x8019D554 < int(end, 16)]
assert overlaps[-1] == (0x8019D434, 0x8019D564, 'func_8019D434')
assert overlaps[0][2] != 'func_8019D434'
report['continuation'] = {'address': '8019D554', 'overlappingBounds': overlaps,
    'firstBoundFunction': overlaps[0][2],
    'interpreterObserved': '[Interp] Interpreting at 0x8019d554' in (output / 'original-compare-native.log').read_text(),
    'limit': 'Earlier broad bounds win before restored wrapper; explicit continuation dispatch routes still required for an all-static path.'}
if args.continuation_routes:
    assembly_path = root.parent / 'dtk-output/asm/auto_03_8018FEA8_text.s'
    assembly = assembly_path.read_text().split('.fn fn_8019D434, global\n', 1)[1].split('.endfn fn_8019D434', 1)[0]
    decoded = [(int(address, 16), int(raw.replace(' ', ''), 16), instruction.strip())
        for address, raw, instruction in re.findall(r'/\* ([0-9A-F]{8}) [0-9A-F]{8}  ([0-9A-F ]{11}) \*/\s*(.*)', assembly)]
    assert [(address, word) for address, word, _ in decoded] == [
        (item['address'], item['word']) for item in build['originalWords']]
    assert [instruction for address, _, instruction in decoded if address == 0x8019D550] == ['bl fn_8019C714']
    assert [instruction for address, _, instruction in decoded if address == 0x8019D560] == ['blr']
    report['dtk'] = {'assemblySha256': sha(assembly_path), 'originalWordsMatched': len(decoded),
        'originalCall': '8019D550 -> 8019C714, return 8019D554', 'limit': 'Static decode, not execution oracle.'}
    routes_text = dispatcher.split('static const DispatchRoute g_dispatch_routes[] = {', 1)[1].split('\n};', 1)[0]
    routes = [(int(address, 16), function) for address, function in
        re.findall(r'\{0x([0-9A-F]+), (\w+)\}', routes_text)]
    assert all(routes[index][0] < routes[index + 1][0] for index in range(len(routes) - 1))
    selected = [(address, function) for address, function in routes if 0x8019D434 <= address < 0x8019D564]
    assert selected == [(0x8019D434, 'dispatch_hle_8019D434')] + [
        (address, 'func_8019D434') for address in range(0x8019D438, 0x8019D564, 4)]
    assert not report['continuation']['interpreterObserved']
    assert (output / 'original-compare-native.log').read_text().count('SCAN_ROUTES 76\n') == 1
    report['continuation']['explicitRoutes'] = 76
    report['continuation']['limit'] = 'Wrapper exact routes verified; global bounds still overlap, no global all-static acceptance.'
if args.tag:
    prefix = root / (variant + '-headless-windowed-' + args.tag)
    if not Path(str(prefix) + '-result.json').exists():
        prefix = root / (variant + '-trace-windowed-' + args.tag)
    run_path, log_path = Path(str(prefix) + '-result.json'), Path(str(prefix) + '.log')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
    assert run['originalDolSha256'] == sha(dol)
    assert run['recipeSha256'] == sha(Path('experiments/wii-static-recomp/run_stock_baseline.py'))
    assert run['variant'] == variant and run['windowed'] and run['capture']
    log = log_path.read_text(errors='replace')
    report['runtime'] = {'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
        'runSha256': sha(run_path), 'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)),
        'planeFrames': re.findall(r'\[THPPlanes\] frame=(\d+)', log), 'gpuHang': 'GPU Hang' in log,
        'statistics': re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log),
        'captures': {str(path): sha(path) for path in sorted(root.glob(variant + '-' + args.tag + '-efb_*.bmp'))}}
    scan_calls = re.findall(r'\[CALL\] 0x8019d434 lr=0x([0-9a-f]+) r3=0x([0-9a-f]+) r4=0x([0-9a-f]+)', log)
    report['runtime']['scanCalls'] = len(scan_calls)
    report['runtime']['scanCallers'] = sorted({caller for caller, _, _ in scan_calls})
    original = dol.read_bytes()
    layout = struct.unpack('>64I', original[:256])
    formats = {}
    for address in sorted({int(fmt, 16) for _, _, fmt in scan_calls}):
        for section in range(18):
            if layout[18 + section] <= address < layout[18 + section] + layout[36 + section]:
                offset = layout[section] + address - layout[18 + section]
                formats[f'{address:08X}'] = original[offset:offset + 120].split(b'\0', 1)[0].decode('ascii')
                break
    report['runtime']['dolFormatStrings'] = formats
    report['runtime']['formatLimit'] = 'Format literals verified in original DOL; runtime argument text and output memory not captured by this trace.'
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], report.get('runtime', 'boot not tested'))
