"""Audit the main-only observer, real GL isolation proof and bounded live capture/log."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-debug-overlay'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
exe = output / 'OpenSHSMStockDebugOverlay'
assert sha(exe) == build['executableSha256']
parent_path = root / 'window-test-profile/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
command = list(parent['linkCommand'])
command[command.index(str(root / 'window-test-profile/main.cpp.o'))] = str(output / 'main.cpp.o')
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand']
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == build['archiveSha256'] == parent['archiveSha256']
source = output / 'main.cpp'
assert sha(source) == build['sourceSha256']
original = source.read_text().replace('#include "stock_debug_overlay.h"\n', '', 1)
for before, after in reversed(build['patches']):
    assert original.count(after) == 1
    original = original.replace(after, before)
assert original == (root / 'window-test-profile/main.cpp').read_text()
dsp_record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled']
    if row['source'] == 'hw_dsp.cpp')
dsp_source = root / 'window-quantization/hw_dsp.cpp'
assert sha(dsp_source) == dsp_record['sourceSha256']
dsp_object = subprocess.run(['/usr/bin/ar', 'p', str(archive), 'hw_dsp.cpp.o'],
    capture_output=True, check=True).stdout
assert hashlib.sha256(dsp_object).hexdigest() == dsp_record['objectSha256']
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'DEBUG_OVERLAY_GL_STATE_EFB_PRESERVED' and component['buildSha256'] == sha(build_path)
run_path = root / 'headless-sc-pc-headless-windowed-debug-overlay-live-result.json'
run = json.loads(run_path.read_text())
assert run['windowed'] and run['debugOverlay'] and run['testABAtMs'] is None
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['executableSha256'] == sha(exe)
log = root / 'headless-sc-pc-headless-windowed-debug-overlay-live.log'
assert sha(log) == run['logSha256']
text = log.read_text(errors='replace')
assert 'overlay shader initialization failed' not in text
rows = []
for match in re.finditer(r'\[AVDebug\] seconds=([\d.]+) present=(\d+) gx=(\d+) queueMinBytes=(\d+) '
    r'empty=(\d+) pulls=(\d+) suppliedFrames=(\d+) short=(\d+) errors=(\d+)', text):
    seconds, *values = match.groups()
    row = dict(zip(['present', 'gx', 'queueMinBytes', 'empty', 'pulls', 'suppliedFrames', 'short', 'errors'], map(int, values)))
    row['seconds'] = float(seconds)
    assert row['seconds'] >= 1 and row['suppliedFrames'] <= row['pulls'] * 1024 and row['short'] <= row['pulls']
    rows.append(row)
assert rows
active = [row for row in rows if row['suppliedFrames'] > 0]
assert active
summary = {'activeIntervals': len(active), 'emptyQueueObservations': sum(row['empty'] for row in active),
    'shortPulls': sum(row['short'] for row in active), 'pulls': sum(row['pulls'] for row in active),
    'queueErrors': sum(row['errors'] for row in rows),
    'outputFpsRange': [min(row['present'] / row['seconds'] for row in active), max(row['present'] / row['seconds'] for row in active)],
    'gxBatchFpsRange': [min(row['gx'] / row['seconds'] for row in active), max(row['gx'] / row['seconds'] for row in active)]}
captures = {}
for bmp in root.glob('headless-sc-pc-debug-overlay-live-efb_debug_*.bmp'):
    png = bmp.with_suffix('.png')
    rgb = Image.open(bmp).convert('RGB')
    rgb.save(png)
    assert Image.open(png).convert('RGB').tobytes() == rgb.tobytes()
    assert Image.open(png).convert('RGBA').getchannel('A').getextrema() == (255, 255)
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
assert captures
(output / 'live-audit.json').write_text(json.dumps({'result': 'DEBUG_OVERLAY_REAL_GL_AND_LIVE_AUDITED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'logSha256': sha(log), 'auditorSha256': sha(Path(__file__).resolve()),
    'dspSourceSha256': sha(dsp_source), 'dspObjectSha256': dsp_record['objectSha256'],
    'rows': rows, 'summary': summary, 'captures': captures,
    'limits': ['GX metric is consumed surviving render batches, not all guest frames or simulation speed percent.',
        'Output metric counts host presents; repeats allowed. Debug/capture overhead, not uninstrumented FPS benchmark.',
        'Active audio means nonzero frames supplied, not sample audibility or exact movie phase; starvation observed, cause not uniquely attributed.',
        'No original Wii hardware/story/profile/controller or audio acceptance; visual inspection separate.']}, indent=2) + '\n')
print('DEBUG_OVERLAY_REAL_GL_AND_LIVE_AUDITED', len(captures))
print(json.dumps(summary, indent=2))
