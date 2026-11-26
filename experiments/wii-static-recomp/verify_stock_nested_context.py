"""Replay observed nested-context pointer selection in actual linked HLE; infer only post-save control fields."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-cache-filtered'
output = root / 'nested-context-fixture'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
analysis_path = base / 'trace-analysis.json'
analysis = json.loads(analysis_path.read_text())
capture = root / 'window-cache-filtered-filtered180-thp-contexts.jsonl'
assert sha(capture) == analysis['captureSha256']
rows = [json.loads(line) for line in capture.read_text().splitlines()]
unfinished = [call for call in analysis['calls'] if call['return'] is None]
assert len(unfinished) == 1
call = unfinished[0]
candidates = [row for row in rows if row['stage'] == 0 and row['pc'] == 0x80212FC4
    and row['lr'] == 0x8009BB9C and row['sp'] == call['entry']['sp']
    and row['selected'] != row['current'] and row['current'] != 0]
assert len(candidates) == 1
row = candidates[0]
nested, thread = row['selected'], row['current']
assert row['saved'] == thread
selected = bytearray.fromhex(row['selectedHex'])
current = bytes.fromhex(row['currentHex'])
assert len(selected) == len(current) == 0x1C8
for offset, value in [(4, row['sp']), (12, row['gpr3']), (16, row['gpr4']), (20, row['gpr5']),
        (0x84, row['lr']), (0x88, row['ctr']), (0x198, row['pc']), (0x19C, row['msr'])]:
    struct.pack_into('>I', selected, offset, value)
fixture = output / 'observed-selection.bin'
fixture.write_bytes(struct.pack('>6I', nested, thread, row['pc'], row['ctr'], row['sp'], row['lr']) + selected + current)
build_path = base / 'build.json'
build = json.loads(build_path.read_text())
assert sha(base / 'OpenSHSMStockCacheFiltered') == build['executableSha256']
command = list(build['linkCommand'])
command[command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
source = Path('experiments/wii-static-recomp/stock_nested_context_probe.cpp').resolve()
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'main_output.cpp')
obj = output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(source), '-o', str(obj)],
    capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command.insert(1, str(obj))
exe = output / 'nested-context-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=60)
result = subprocess.run([str(exe), str(fixture)], capture_output=True, text=True, timeout=20)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
(output / 'comparison.json').write_text(json.dumps({'result': 'OBSERVED_NESTED_SELECTION_DIVERGENCE_REPRODUCED',
    'captureSha256': sha(capture), 'analysisSha256': sha(analysis_path), 'buildSha256': sha(build_path),
    'sourceSha256': sha(source), 'executableSha256': sha(exe), 'fixtureSha256': sha(fixture),
    'logSha256': sha(output / 'probe.log'), 'recipeSha256': sha(Path(__file__)), 'observedSaveRow': row,
    'linkCommand': command, 'output': result.stdout,
    'limits': ['Actual HLE pointer-selection replay, not complete nested IRQ execution or physical Wii behavior.',
        'Post-save PC/SP/LR/CTR/GPR3..5/MSR inferred from observed live controls and current serializer; other temporary fields are supplied.',
        'Current thread raw snapshot is observed; selecting it loses the captured cache continuation in this finite fixture.',
        'Live select-before/load-after for the same interrupted activation was not fully recorded; causal acceptance remains pending.',
        'No runtime repair/forced state/game launch or production change.']}, indent=2) + '\n')
print('OBSERVED_NESTED_SELECTION_DIVERGENCE_REPRODUCED')
print(result.stdout)
