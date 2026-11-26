"""Audit absolute-deadline integration, unchanged legacy scheduler text and actual bounded capture/run."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-adma-deadline'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
parent_path = root / 'window-adma-accounting/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
source = output / 'hw_dsp.cpp'
assert sha(source) == build['sourceSha256']
restored = source.read_text()
for before, after in reversed(build['patches']):
    assert restored.count(after) == 1
    restored = restored.replace(after, before)
assert restored == (root / 'window-adma-accounting/hw_dsp.cpp').read_text()
scheduler = output / 'event_scheduler.cpp'
assert sha(scheduler) == build['schedulerSourceSha256']
assert scheduler.read_text().replace(build['schedulerAddition'], '', 1) == (root / 'window-quantization/event_scheduler.cpp').read_text()
before, after = build['schedulerHeaderPatch']
assert (output / 'include/runtime/event_scheduler.h').read_text().replace(after, before, 1) == (
    root / 'export/nWiiRuntime/include/runtime/event_scheduler.h').read_text()
archive = output / 'libnwiiruntime.a'
exe = output / 'OpenSHSMStockADMADeadline'
assert sha(archive) == build['archiveSha256'] and sha(exe) == build['executableSha256']
names = [name for name in subprocess.run(['/usr/bin/ar', 't', str(archive)], check=True,
    capture_output=True, text=True).stdout.splitlines() if name.endswith('.o')]
assert set(names) == set(parent['members']) and len(names) == len(set(names))
for name in names:
    digest = hashlib.sha256(subprocess.run(['/usr/bin/ar', 'p', str(archive), name], check=True, capture_output=True).stdout).hexdigest()
    assert digest == build['members'][name]
    if name not in ('hw_dsp.cpp.o', 'event_scheduler.cpp.o'):
        assert digest == parent['members'][name]
command = list(parent['linkCommand'])
command[command.index(str(root / 'window-adma-accounting/libnwiiruntime.a'))] = str(archive)
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand']
component_path = root / 'adma-deadline-research/verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'ADMA_DEADLINE_BATCH_REGULAR_PCM_EQUAL64'
assert len([row for row in component['rows'] if row['variant'] == 'candidate']) == 64
assert all(row['buildSha256'] == sha(build_path) for row in component['rows'] if row['variant'] == 'candidate')
run_path = root / 'headless-sc-pc-headless-windowed-adma-deadline-live-result.json'
run = json.loads(run_path.read_text())
assert run['wallTimebase'] and run['windowed'] and run['capture'] and run['dspSupply']
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['executableSha256'] == sha(exe)
log = root / 'headless-sc-pc-headless-windowed-adma-deadline-live.log'
assert sha(log) == run['logSha256']
fields = ['wallUs', 'input32', 'input48', 'accepted', 'dropped', 'flushAccepted', 'flushDropped',
    'supplied', 'requested', 'short', 'ring', 'tbFirst', 'tbLast', 'tbFrequency', 'tbWallUs']
text = log.read_text(errors='replace')
rows = [dict(zip(fields, map(int, match.groups()))) for match in re.finditer(
    r'\[ADMAAccounting\] ' + ' '.join(name + r'=(\d+)' for name in fields), text)]
assert rows
for row in rows:
    assert row['accepted'] - row['supplied'] == row['ring']
    if not row['input48']:
        assert row['input32'] == row['accepted'] + row['dropped']
last = rows[-1]
ratio = (last['tbLast'] - last['tbFirst']) * 1000000 / (last['tbFrequency'] * last['tbWallUs'])
assert 0.99 < ratio < 1.01
captures = {}
for bmp in root.glob('headless-sc-pc-adma-deadline-live-efb_debug_*.bmp'):
    png = bmp.with_suffix('.png')
    rgb = Image.open(bmp).convert('RGB')
    rgb.save(png)
    assert Image.open(png).convert('RGB').tobytes() == rgb.tobytes()
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
assert captures
(output / 'live-audit.json').write_text(json.dumps({'result': 'ADMA_DEADLINE_SOURCE_COMPONENT_LIVE_AUDITED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'logSha256': sha(log), 'auditorSha256': sha(Path(__file__).resolve()),
    'rows': rows, 'last': last, 'configuredTbToWallRatio': ratio, 'captures': captures,
    'limits': ['Two runtime objects only, scheduler legacy methods/heap/data layout text unchanged; additive absolute API.',
        'Controlled chronology/PCM/count/stop equivalence, not original CPU IRQ-handler interleaving/physical Wii oracle.',
        'Actual audio balance and wallTB observed; frames/runs differ, no controlled FPS/complete sound improvement claim.',
        'Capture inspection separate, no listening/profile/story/controller/default/release promotion.']}, indent=2) + '\n')
print('ADMA_DEADLINE_SOURCE_COMPONENT_LIVE_AUDITED', len(captures))
print(json.dumps({'last': last, 'configuredTbToWallRatio': ratio}, indent=2))
