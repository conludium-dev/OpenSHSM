"""Describe captured cache call progress without equating missing records with absent IRQ execution."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--variant', choices=['window-cache-filtered', 'window-legacy-context'], default='window-cache-filtered')
args = parser.parse_args()
tag = 'legacy180' if args.variant == 'window-legacy-context' else 'filtered180'

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / args.variant
capture = root / (args.variant + '-' + tag + '-thp-contexts.jsonl')
rows = [json.loads(line) for line in capture.read_text().splitlines()]
calls = []
active = {}
orphans = []
for row in rows:
    stage = row['stage']
    if stage not in (4, 5, 6, 7):
        continue
    key = row['sp']
    if stage == 4:
        if key in active:
            calls[active[key]]['replacedWithoutObservedReturn'] = True
        index = len(calls)
        calls.append({'index': index, 'entry': row, 'pre': [], 'post': [], 'return': None})
        active[key] = index
    elif key not in active:
        orphans.append(row)
    else:
        call = calls[active[key]]
        if stage == 5:
            call['pre'].append(row)
        elif stage == 6:
            call['post'].append(row)
        elif stage == 7:
            call['return'] = row
            del active[key]
for call in calls:
    entry = call['entry']
    size, address = entry['gpr4'], entry['gpr3']
    blocks = ((size + (address & 31) + 31) & 0xFFFFFFFF) >> 5
    result = call['return']
    call['expectedBlocks'] = blocks
    call['sampledPreCtr'] = [row['ctr'] for row in call['pre']]
    call['sampledPostCtr'] = [row['ctr'] for row in call['post']]
    call['returnRegisterMatch'] = result is not None and size != 0 and blocks != 0
    if call['returnRegisterMatch']:
        call['returnRegisterMatch'] = result['ctr'] == 0 and result['gpr4'] == blocks
        call['returnRegisterMatch'] = call['returnRegisterMatch'] and result['gpr3'] == ((address + 32 * blocks) & 0xFFFFFFFF)
    call['localPrePostMatches'] = sum(before['ctr'] == after['ctr'] and before['gpr3'] == after['gpr3']
        for before, after in zip(call['pre'], call['post']))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'CACHE_TRACE_DESCRIPTIVE_ANALYSIS', 'captureSha256': sha(capture),
    'recipeSha256': sha(Path(__file__)), 'events': len(rows),
    'stageCounts': dict(Counter(row['stage'] for row in rows)), 'calls': calls, 'orphanRows': orphans,
    'limits': ['Calls grouped by observed SP and fixed caller LR, not original IRQ activation identities.',
        'Zero-length early return is outside FC8 hook; sampled missing return does not prove permanent deadlock.',
        'Pre/post arrays may contain repeated interrupted PCs and sampling gaps; zipped matches are only descriptive.',
        'Expected block arithmetic derives from checked original SDK kernel, not proof of cache coherence or IRQ scheduling.']}
(output / 'trace-analysis.json').write_text(json.dumps(report, indent=2) + '\n')
print('CACHE_TRACE_DESCRIPTIVE_ANALYSIS', len(calls), 'calls', len(orphans), 'orphans')
for call in calls:
    print(call['index'], 'sp', hex(call['entry']['sp']), 'size', call['entry']['gpr4'],
        'pre', call['sampledPreCtr'], 'post', call['sampledPostCtr'],
        'returnMatch', call['returnRegisterMatch'])
