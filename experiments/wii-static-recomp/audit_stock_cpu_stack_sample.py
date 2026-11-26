"""Compute exclusive stack-hit counts on the verified emulated CPU thread only."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
args = parser.parse_args()
artifacts = args.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp') and re.fullmatch(r'openshsm-run-[A-Za-z0-9_-]+', artifacts.name)
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
run_path = artifacts / 'headless-sc-pc-headless-windowed-post-present-profile-result.json'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['cpuSampleReturncode'] == 0
execution_path = artifacts / 'cpu-sample-execution.json'
execution = json.loads(execution_path.read_text())
assert execution['result'] == 'OWNED_RUNTIME_READ_ONLY_CPU_STACK_SAMPLE_COLLECTED'
assert execution['pid'] == run['pid'] and execution['executableSha256'] == run['executableSha256']
assert not execution['toolTimedOut'] and execution['toolReturncode'] == 0
profile_path = Path(execution['profilePath'])
assert profile_path.parent == artifacts and sha(profile_path) == execution['profileSha256']
assert sha(Path(execution['toolLogPath'])) == execution['toolLogSha256']
text = profile_path.read_text()
graph = text[text.index('Call graph:'):text.index('Sort by top of stack')]
roots = list(re.finditer(r'^    (\d+) Thread_([^\n]+)', graph, re.M))
blocks = [graph[row.start():roots[index + 1].start() if index + 1 < len(roots) else len(graph)]
    for index, row in enumerate(roots)]
cpu = [block for block in blocks if 'cpu_thread_func(' in block]
assert len(cpu) == 1
nodes = []
stack = []
for line in cpu[0].splitlines():
    match = re.match(r'^([ +!:|]+)(\d+) (.+)$', line)
    if not match:
        continue
    depth, count, label = len(match[1]), int(match[2]), match[3]
    symbol = label.split('  (in ', 1)[0]
    while stack and nodes[stack[-1]]['depth'] >= depth:
        stack.pop()
    parent = stack[-1] if stack else None
    node = {'depth': depth, 'count': count, 'symbol': symbol, 'children': [], 'parent': parent}
    index = len(nodes)
    nodes.append(node)
    if parent is not None:
        nodes[parent]['children'].append(index)
    stack.append(index)
assert nodes and nodes[0]['symbol'].startswith('Thread_')
total = nodes[0]['count']
exclusive = collections.Counter()
env_parents = collections.Counter()
clock_parents = collections.Counter()
for index, node in enumerate(nodes):
    own = node['count'] - sum(nodes[child]['count'] for child in node['children'])
    assert own >= 0, node
    exclusive[node['symbol']] += own
    if own and (node['symbol'] == '__findenv_locked' or node['symbol'].startswith('mach_continuous_time')):
        lineage = []
        parent = node['parent']
        while parent is not None:
            lineage.append(nodes[parent]['symbol'])
            parent = nodes[parent]['parent']
        nearest = next((label for label in lineage if label.startswith(('nwii::', 'stock_', 'func_', 'observe_'))), 'unresolved')
        (env_parents if node['symbol'] == '__findenv_locked' else clock_parents)[nearest] += own
assert sum(exclusive.values()) == total
top = [{'symbol': label, 'exclusiveHits': count, 'sharePercent': count * 100 / total}
    for label, count in exclusive.most_common(20) if count]
timing_path = artifacts / 'headless-sc-pc-post-present-profile-movie-timing.jsonl'
timing = [json.loads(line) for line in timing_path.read_text().splitlines()]
overlap = [row for row in timing if execution['startHostUs'] <= row['hostUs'] <= execution['endHostUs']]
decoder_stack_present = any(node['symbol'].startswith('func_80209D80') for node in nodes)
assert decoder_stack_present
report = {'result': 'OWNED_CPU_THREAD_EXCLUSIVE_STACK_HITS_AUDITED',
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), run_path, execution_path, profile_path, timing_path]},
    'cpuThread': nodes[0]['symbol'], 'cpuSamples': total, 'nodeCount': len(nodes),
    'sampleToolIntervalUs': execution['endHostUs'] - execution['startHostUs'],
    'topExclusive': top, 'environmentLookupCallers': dict(env_parents), 'clockCallers': dict(clock_parents),
    'overlappingMovieEvents': len(overlap), 'overlappingDecoderBegins': sum(row['site'] == 0x80209D80 for row in overlap),
    'decoderPresentInCpuStacks': decoder_stack_present,
    'limits': ['Tree child counts subtracted; exclusive counts partition ONLY the sampled CPU thread, not global GUI/audio totals.',
        'Statistical stack-hit share, not exact CPU duration or complete decoder-exclusive attribution.',
        'Decoder appears in actual CPU stacks; delayed movie gate may mean no captured boundary intervals overlap the OS sample.',
        'No per-frame attribution without overlapping interval evidence; do not add disjoint packet timings to stack-hit shares.',
        'Unwinding/tail calls/inlining and profiler perturbation limit attribution; no optimization or physical Wii behavior proof.']}
path = artifacts / 'cpu-stack-audit.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps({'cpuSamples': total, 'top': top[:10], 'env': dict(env_parents), 'clocks': dict(clock_parents)}, indent=2))
