"""Check actual observer provenance and decode bounded stage snapshots."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import subprocess
from stock_idct_observation import adapt_idct
from stock_dcbz_lowering import lower_dcbz

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--dcbz', action='store_true')
args = parser.parse_args()
assert args.tag is None or re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-quantization'
variant = 'window-thp-dcbz' if args.dcbz else 'window-idct-observe'
output = root / variant
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
parent = json.loads((base / 'build.json').read_text())
assert sha(base / 'build.json') == build['baseBuildSha256']
assert sha(base / 'include/runtime/cpu_context.h') == parent['cpuHeaderSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
text, sites = adapt_idct((base / 'output_37.cpp').read_text(), dol_path.read_bytes())
if args.dcbz:
    text, zero_sites = lower_dcbz(text, dol_path.read_bytes())
    assert zero_sites == build['zeroSites']
assert text == (output / 'output_37.cpp').read_text() and sites == build['sites']
assert sha(output / 'output_37.cpp') == build['sourceSha256']
assert sha(output / 'output_37.cpp.o') == build['objectSha256']
assert build['arguments'] == next(row['arguments'] for row in parent['compiled'] if row['source'] == 'output_37.cpp')
assert len(build['retainedObjects']) == 76
assert all(sha(Path(path)) == expected for path, expected in build['retainedObjects'].items())
assert sha(base / 'libnwiiruntime.a') == build['archiveSha256']
exe_name = 'OpenSHSMStockTHPDCBZ' if args.dcbz else 'OpenSHSMStockIDCTObserver'
assert sha(output / exe_name) == build['executableSha256']
expected_link = list(parent['linkCommand'])
expected_link[expected_link.index(str(base / 'output_37.cpp.o'))] = str(output / 'output_37.cpp.o')
expected_link[expected_link.index('-o') + 1] = str(output / exe_name)
assert expected_link == build['linkCommand']
report = {'result': 'THP_DCBZ_PROVENANCE_PASS' if args.dcbz else 'READ_ONLY_IDCT_OBSERVER_PROVENANCE_PASS', 'sites': len(sites), 'limits': build['limits']}
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
def dol_bytes(address, length):
    section = next(i for i in range(18) if layout[18 + i] <= address and address + length <= layout[18 + i] + layout[36 + i])
    offset = layout[section] + address - layout[18 + section]
    return dol[offset:offset + length]
zero_sites = []
for address, word in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})\n    // dcbz \(data cache block zero\) - stub', (base / 'output_37.cpp').read_text()):
    address, word = int(address, 16), int(word, 16)
    assert dol_bytes(address, 4) == struct.pack('>I', word)
    assert word >> 26 == 31 and ((word >> 1) & 1023) == 1014
    zero_sites.append({'address': hex(address), 'word': hex(word), 'ra': (word >> 16) & 31, 'rb': (word >> 11) & 31})
report['originalDcbzSites'] = zero_sites
report['dcbzImplemented'] = args.dcbz
if args.dcbz:
    contract = json.loads((output / 'contract.json').read_text())
    assert contract['parentBuildSha256'] == sha(output / 'build.json')
    assert contract['cpuHeaderSha256'] == parent['cpuHeaderSha256']
    assert contract['sourceSha256'] == sha(Path('experiments/wii-static-recomp/stock_dcbz_contract.cpp'))
    assert contract['dependencySourceSha256'] == sha(Path('experiments/wii-static-recomp/stock_quantization_contract.cpp'))
    assert contract['generatedHeaderSha256'] == sha(output / 'dcbz-sites.h')
    assert contract['executableSha256'] == sha(output / 'dcbz-contract')
    test = subprocess.run([str(output / 'dcbz-contract')], capture_output=True, text=True, timeout=20)
    assert test.returncode == 0 and test.stdout.strip() == contract['output']
    report['contract'] = test.stdout.strip()
if args.tag:
    prefix = root / (variant + '-headless-windowed-' + args.tag)
    log_path, run_path = Path(str(prefix) + '.log'), Path(str(prefix) + '-result.json')
    run = json.loads(run_path.read_text())
    assert sha(log_path) == run['logSha256'] and run['executableSha256'] == build['executableSha256']
    assert run['originalDolSha256'] == sha(dol_path)
    records = []
    for match in re.finditer(r'\[IDCTState\] ([^\n]+)', log_path.read_text(errors='replace')):
        row = dict(re.findall(r'(\w+)=(\S+)', match[1]))
        if not all(key in row for key in ('kind', 'hit', 'pc', 'gqr0', 'gqr5', 'gqr6', 'data', 'qdata', 'constants', 'fpr')):
            continue
        pairs = row['fpr'].split(';')[:-1]
        if len(pairs) != 32:
            continue
        row['fprValues'] = [[float.fromhex(value) for value in pair.split(',')] for pair in pairs]
        for field in ('qdata', 'constants'):
            if row[field] != '-':
                data = bytes.fromhex(row[field])
                row[field + 'Floats'] = list(struct.unpack('>' + 'f' * (len(data) // 4), data))
        if row['constants'] != '-':
            row['constantsMatchDol'] = bytes.fromhex(row['constants']) == dol_bytes(int(row['r2'], 16) - 19232, 20)
        if row['kind'] == 'entry' and row['pc'] in ('8020afd0', '8020b460') and row['data'] != '-':
            row['coefficientValues'] = list(struct.unpack('>64h', bytes.fromhex(row['data'])))
        records.append(row)
    report.update(returncode=run['terminalReturncode'], deadlineReached=run['deadlineReached'],
        records=records, runSha256=sha(run_path))
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 'records=', len(report.get('records', [])))
if args.tag:
    for row in report['records'][:8]:
        print(row['kind'], row['pc'], 'GQR', row['gqr0'], row['gqr5'], row['gqr6'],
            'FPR9=', row['fprValues'][9], 'constants=', row.get('constantsFloats'))
