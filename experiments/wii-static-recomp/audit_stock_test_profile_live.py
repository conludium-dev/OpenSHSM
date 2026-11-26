"""Pin actual input events/captures and unchanged guest/runtime inputs; UI inspection stays separate."""
from pathlib import Path
import hashlib
import json
import re
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-test-profile'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
exe = output / 'OpenSHSMStockTestProfile'
assert sha(exe) == build['executableSha256']
component = output / 'component-verification.json'
proof = json.loads(component.read_text())
assert proof['result'] == 'PRIVATE_PROFILE_BOUNDARIES_QUEUE_PASS' and proof['buildSha256'] == sha(build_path)
parent_path = root / 'window-test-ab/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
command = list(parent['linkCommand'])
command[command.index(str(root / 'window-test-ab/main.cpp.o'))] = str(output / 'main.cpp.o')
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand']
archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
assert sha(archive) == build['archiveSha256'] == parent['archiveSha256']
source = output / 'main.cpp'
assert sha(source) == build['sourceSha256']
assert source.read_text().replace('stock_test_profile_source.h', 'stock_test_ab_source.h').replace(
    'install_test_profile_source(', 'install_test_ab_source(') == (root / 'window-test-ab/main.cpp').read_text()
run_path = root / 'headless-sc-pc-headless-windowed-profile-select-live-result.json'
run = json.loads(run_path.read_text())
assert run['testABAtMs'] == 95000 and run['testSelectAtMs'] == 125000 and run['windowed']
assert run['executableSha256'] == sha(exe) and run['terminalReturncode'] == 0 and run['deadlineReached']
log = root / 'headless-sc-pc-headless-windowed-profile-select-live.log'
assert sha(log) == run['logSha256']
events = [(int(time), int(buttons)) for time, buttons in re.findall(
    r'\[TestProfile\] elapsedMs=(\d+) buttons=(\d+)', log.read_text(errors='replace'))]
assert [buttons for _, buttons in events] == [0xC00, 0, 0x800, 0], events
assert all(time >= minimum for (time, _), minimum in zip(events, [95000, 95750, 125000, 125750]))
captures = {}
for bmp in root.glob('headless-sc-pc-profile-select-live-efb_*.bmp'):
    png = bmp.with_suffix('.png')
    pixels = Image.open(bmp).convert('RGBA')
    pixels.save(png)
    assert Image.open(png).convert('RGBA').tobytes() == pixels.tobytes()
    display = bmp.with_suffix('.display.png')
    rgb = pixels.convert('RGB')
    rgb.save(display)
    assert Image.open(display).convert('RGB').tobytes() == rgb.tobytes()
    assert Image.open(display).convert('RGBA').getchannel('A').getextrema() == (255, 255)
    captures[bmp.stem] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png),
        'displayPngSha256': sha(display), 'rawAlphaRange': pixels.getchannel('A').getextrema()}
assert captures
(output / 'live-audit.json').write_text(json.dumps({
    'result': 'PRIVATE_PROFILE_SOURCE_LIVE_CAPTURE_AUDITED', 'events': events, 'captures': captures,
    'buildSha256': sha(build_path), 'componentSha256': sha(component), 'runSha256': sha(run_path),
    'logSha256': sha(log), 'auditorSha256': sha(Path(__file__).resolve()),
    'limits': ['One A+B and one A pulse through actual manager, original menus/75guests/runtime retained.',
        'Raw RGBA evidence preserved; separate opaque RGB display preview preserves every RGB byte.',
        'Visual state inspected separately; no physical controller/persistence/story/FPS/brightness acceptance.']}, indent=2) + '\n')
print('PRIVATE_PROFILE_SOURCE_LIVE_CAPTURE_AUDITED', len(captures), events)
