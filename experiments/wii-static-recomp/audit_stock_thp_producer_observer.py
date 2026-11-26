"""Audit producer/SDK boundary provenance and observed guard/callback states."""
from pathlib import Path
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import re
from stock_thp_producer_observation import adapt
from stock_thp_chain_observation import adapt as adapt_chain, chain_header
from stock_thp_dma_observation import adapt as adapt_dma, dma_header

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
parser.add_argument('--chain', action='store_true')
parser.add_argument('--dma', action='store_true')
args = parser.parse_args()
args.chain = args.chain or args.dma
assert re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
variant = 'window-movie-chain' if args.chain else 'window-movie-producer'
if args.dma:
    variant = 'window-movie-dma'
output = root / variant
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['baseBuildSha256'] == sha(root / 'window-movie-update/build.json')
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
for item in build['records']:
    original = Path(item['originalPath'])
    source = output / f'output_{item["module"]}.cpp'
    assert sha(original) == item['originalSha256']
    assert source.read_text() == (adapt_dma if args.dma else adapt_chain if args.chain else adapt)(original.read_text(), dol.read_bytes(), item['module'])
    assert sha(source) == item['sourceSha256'] and sha(Path(str(source) + '.o')) == item['objectSha256']
assert sha(Path('experiments/wii-static-recomp/stock_thp_producer_observation.h')) == build['headerSha256']
if args.chain:
    header_name = 'stock_thp_dma_observation.h' if args.dma else 'stock_thp_chain_observation.h'
    assert (output / header_name).read_text() == (dma_header if args.dma else chain_header)(Path('experiments/wii-static-recomp/stock_thp_producer_observation.h').read_text())
    assert sha(output / header_name) == build['chainHeaderSha256']
assert sha(Path('experiments/wii-static-recomp/stock_thp_queue_observation.h')) == build['queueHeaderSha256']
assert sha(output / ('OpenSHSMStockMovieDMA' if args.dma else 'OpenSHSMStockMovieChain' if args.chain else 'OpenSHSMStockMovieProducer')) == build['executableSha256']
for path, digest in build['retainedInputs'].items():
    assert sha(Path(path)) == digest
component = json.loads((output / 'component.json').read_text())
assert component['result'] == 'MOVIE_PRODUCER_HELPER_COMPONENT_PASS' and component['events'] == (87 if args.dma else 81 if args.chain else 11)
assert component['buildSha256'] == sha(output / 'build.json')
assert sha(Path('experiments/wii-static-recomp/stock_thp_chain_contract.cpp' if args.chain
    else 'experiments/wii-static-recomp/stock_thp_producer_contract.cpp')) == component['sourceSha256']
if args.dma:
    text = Path('experiments/wii-static-recomp/stock_thp_chain_contract.cpp').read_text().replace('"stock_thp_chain_observation.h"', '"stock_thp_dma_observation.h"')
    text = text.replace('0x8009BB48u, 0x8009BB4Cu, 0x8009BAECu, 0x8009BBBCu})',
        '0x8009BB48u, 0x8009BB4Cu, 0x8009BAECu, 0x8009BBBCu,\n'
        '        0x8009BB34u, 0x8009BB58u, 0x8009BB7Cu, 0x8009BB80u, 0x8009BB9Cu, 0x8009BBB8u})')
    assert (output / 'dma-contract.cpp').read_text() == text
    assert sha(output / 'dma-contract.cpp') == component['compiledSourceSha256']
for name, field in [('observer-contract', 'executableSha256'), ('contract.cpp.o', 'objectSha256'),
    ('contract.log', 'logSha256')]:
    assert sha(output / name) == component[field]
assert sha(Path(component.get('capturePath', str(output / 'component-movie-producer.jsonl')))) == component['captureSha256']
label = variant + '-headless-windowed-' + args.tag
run_path, log_path = root / (label + '-result.json'), root / (label + '.log')
run = json.loads(run_path.read_text())
assert run['executableSha256'] == build['executableSha256'] and run['logSha256'] == sha(log_path)
assert run['recipeSha256'] == sha(Path('experiments/wii-static-recomp/run_stock_baseline.py'))
assert run['originalDolSha256'] == sha(dol)
prefix = root / (variant + '-' + args.tag + '-thp')
capture = Path(str(prefix) + '-movie-producer.jsonl')
rows = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
groups = defaultdict(list)
for index, row in enumerate(rows):
    assert row['serial'] == index
    if len(row['sdkStateHex']) == 112:
        row['guard'] = int(row['sdkStateHex'][:8], 16)
        row['callbackHex'] = row['sdkStateHex'][-8:]
        row['stackHookHex'] = row['sdkStateHex'][96:104]
    else:
        row['guard'] = None
        row['callbackHex'] = None
        row['stackHookHex'] = None
    groups[row['pc']].append(row)
    if args.chain:
        row['previousCallbackHex'] = row['chainHex'][16:24] if len(row['chainHex']) == 56 else None
        row['modeHex'] = row['chainHex'][40:48] if len(row['chainHex']) == 56 else None
summary = [{'pc': f'{pc:08X}', 'samples': len(items), 'lastObservedHit': items[-1]['hits'],
    'guards': dict(Counter(str(row['guard']) for row in items)),
    'callbacks': dict(Counter(str(row['callbackHex']) for row in items)),
    'phaseChanges': sum(row.get('phaseChanged', False) for row in items), 'last': items[-1]}
    for pc, items in groups.items()]
log = log_path.read_text(errors='replace')
report = {'result': 'MOVIE_PRODUCER_OBSERVER_PROVENANCE_AUDIT_PASS', 'events': len(rows),
    'eventCapReached': len(rows) == 8192, 'groups': summary,
    'buildSha256': sha(output / 'build.json'), 'componentSha256': sha(output / 'component.json'),
    'runSha256': sha(run_path), 'captureSha256': sha(capture) if capture.exists() else None,
    'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
    'decoderCalls': len(re.findall(r'\[CALL\] 0x80209d80 ', log)),
    'statistics': re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log),
    'captures': {str(path): sha(path) for path in root.glob(variant + '-' + args.tag + '-efb_*.bmp')},
    'otherObservationFiles': {str(path): sha(path) for path in root.glob(variant + '-' + args.tag + '-thp-*')},
    'limits': build['limits'] + component['limits']}
(output / ('audit-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 'events', len(rows))
print(json.dumps([{key: group[key] for key in ('pc', 'samples', 'lastObservedHit', 'guards', 'callbacks')}
    for group in summary], indent=2))
