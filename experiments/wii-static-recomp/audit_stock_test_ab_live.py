"""Verify scoped timed input registration, retained runtime/guests and actual captured UI."""
from pathlib import Path
import hashlib
import json
import re
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-test-ab'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
exe = output / 'OpenSHSMStockTestAB'
assert sha(exe) == build['executableSha256']
parent_path = root / 'headless-texture-eviction/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['baseBuildSha256']
command = list(parent['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(str(old))] = str(output / 'main.cpp.o')
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand']
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == build['archiveSha256'] == parent['archiveSha256']
source = output / 'main.cpp'
assert sha(source) == build['sourceSha256']
assert source.read_text().replace('#include "stock_test_ab_source.h"\n', '', 1).replace(
    '  openshsm::experiment::install_test_ab_source(nwii::runtime::input::InputManager::get());\n', '', 1) == old.with_suffix('').read_text()
component_path = output / 'component-verification.json'
assert json.loads(component_path.read_text())['result'] == 'PRIVATE_AB_SOURCE_BOUNDARIES_QUEUE_PASS'
run_path = root / 'headless-sc-pc-headless-windowed-test-ab-live-result.json'
run = json.loads(run_path.read_text())
assert run['testABAtMs'] == 95000 and run['executableSha256'] == sha(exe) and run['windowed']
log = root / 'headless-sc-pc-headless-windowed-test-ab-live.log'
assert sha(log) == run['logSha256']
text = log.read_text(errors='replace')
events = [(int(time), int(pressed)) for time, pressed in re.findall(r'\[TestAB\] elapsedMs=(\d+) pressed=(\d)', text)]
assert len(events) == 2 and [value for _, value in events] == [1, 0]
assert events[0][0] >= 95000 and events[1][0] >= 95750
captures = {}
for bmp in root.glob('headless-sc-pc-test-ab-live-efb_*.bmp'):
    png = bmp.with_suffix('.png')
    image = Image.open(bmp).convert('RGBA')
    image.save(png)
    assert Image.open(png).convert('RGBA').tobytes() == image.tobytes()
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
assert captures
(output / 'live-audit.json').write_text(json.dumps({'result': 'PRIVATE_AB_SOURCE_PUBLICATION_LIVE_CAPTURE_AUDITED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'runSha256': sha(run_path),
    'logSha256': sha(log), 'events': events, 'captures': captures, 'auditorSha256': sha(Path(__file__).resolve()),
    'limits': ['Test source registered through existing manager, one press/release, allruntime/all75guests retained.',
        'No OS input/focus or menu state force; visual transition inspected separately, no physical controller/persistence/story claim.']}, indent=2) + '\n')
print('PRIVATE_AB_SOURCE_PUBLICATION_LIVE_CAPTURE_AUDITED', len(captures), events)
