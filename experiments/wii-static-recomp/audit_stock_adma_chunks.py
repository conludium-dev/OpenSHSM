"""Audit integrated two-object backend and bounded run without treating old cap metrics as valid."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-adma-chunks'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
parent_path = root / 'window-dsp-supply/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
for row in build['compiled']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
dsp = (output / 'hw_dsp.cpp').read_text().replace('#include "stock_adma_cursor.h"\n#include "stock_adma_output.h"\n', '', 1)
for before, after in reversed(build['patches']):
    assert dsp.count(after) == 1
    dsp = dsp.replace(after, before)
assert dsp == (root / 'window-dsp-supply/hw_dsp.cpp').read_text()
before, after = build['aiPatch']
assert (output / 'hw_ai.cpp').read_text().replace(after, before, 1) == (root / 'window-quantization/hw_ai.cpp').read_text()
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'hw_ai.cpp')
assert parent['derivedArchiveMembers']['hw_ai.cpp.o'] == record['objectSha256']
archive = output / 'libnwiiruntime.a'
assert sha(archive) == build['archiveSha256']
names = [name for name in subprocess.run(['/usr/bin/ar', 't', str(archive)], check=True,
    capture_output=True, text=True).stdout.splitlines() if name.endswith('.o')]
assert set(names) == set(build['members']) and len(names) == len(set(names))
for name in names:
    digest = hashlib.sha256(subprocess.run(['/usr/bin/ar', 'p', str(archive), name], check=True, capture_output=True).stdout).hexdigest()
    assert digest == build['members'][name]
    if name not in ('hw_dsp.cpp.o', 'hw_ai.cpp.o'):
        assert digest == parent['derivedArchiveMembers'][name]
command = list(parent['linkCommand'])
command[command.index(str(root / 'window-dsp-supply/libnwiiruntime.a'))] = str(archive)
exe = output / 'OpenSHSMStockADMAChunks'
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand'] and sha(exe) == build['executableSha256']
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path) and component['result'] == 'ADMA_CHUNKS_SDK_PCM_IRQ_RATE_PASS'
run_path = root / 'headless-sc-pc-headless-windowed-adma-chunks-live-result.json'
run = json.loads(run_path.read_text())
assert run['windowed'] and run['debugOverlay'] and run['dspSupply'] and not run['capture']
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['executableSha256'] == sha(exe)
log = root / 'headless-sc-pc-headless-windowed-adma-chunks-live.log'
assert sha(log) == run['logSha256']
text = log.read_text(errors='replace')
fields = ['elapsedMs', 'events', 'producedFrames', 'cappedFrames', 'blockFrames', 'periodTicks',
    'maxLateTicks', 'missedPeriods', 'maxGapUs', 'pulls', 'requestedFrames', 'suppliedFrames', 'short', 'maxRingFrames']
rows = [dict(zip(fields, map(int, match.groups()))) for match in re.finditer(
    r'\[DSPSupply\] ' + ' '.join(name + r'=(\d+)' for name in fields), text)]
assert len(rows) > 2
active = [row for row in rows if row['events']]
assert active and all(row['periodTicks'] in (15187, 15188) for row in active)
av = [dict(zip(['seconds', 'present', 'gx', 'queueMinBytes', 'empty', 'pulls', 'suppliedFrames', 'short', 'errors'],
    [float(match[1]), *map(int, match.groups()[1:])])) for match in re.finditer(
    r'\[AVDebug\] seconds=([\d.]+) present=(\d+) gx=(\d+) queueMinBytes=(\d+) empty=(\d+) '
    r'pulls=(\d+) suppliedFrames=(\d+) short=(\d+) errors=(\d+)', text)]
assert av
summary = {'supplyRows': len(rows), 'lastSupply': active[-1], 'avIntervals': len(av),
    'emptyQueueObservations': sum(row['empty'] for row in av),
    'shortPulls': sum(row['short'] for row in av), 'queueErrors': sum(row['errors'] for row in av),
    'capMetricValid': False}
(output / 'live-audit.json').write_text(json.dumps({'result': 'ADMA_CHUNKS_INTEGRATION_COMPONENT_LIVE_AUDITED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'logSha256': sha(log), 'auditorSha256': sha(Path(__file__).resolve()), 'rows': rows, 'avRows': av, 'summary': summary,
    'limits': ['Only DSP+AI objects changed; all75guests/main/other runtime/source transformations verified.',
        'Output conversion/flush can discard at ring cap; old produced() API passed admitted=true, cappedFrames is INVALID.',
        'Sampled period32k, no assertion that every earlier event used same rate, no speedup comparison against different frame runs.',
        'No screenshot/human listening/original Wii timing or complete audible/FPS/profile/controller/story acceptance.']}, indent=2) + '\n')
print('ADMA_CHUNKS_INTEGRATION_COMPONENT_LIVE_AUDITED')
print(json.dumps(summary, indent=2))
