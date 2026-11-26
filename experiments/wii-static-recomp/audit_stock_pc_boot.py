"""Pin the real opt-in boot and opaque default-window captures; visual inspection remains separate."""
from pathlib import Path
import hashlib
import json
from PIL import Image

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-pc-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
component_path = output / 'verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['result'] in ('PC_BOOT_ADAPTER85_CASES_SOURCE_RETENTION_PASS',
    'PC_BOOT_ADAPTER95_CASES_SOURCE_RETENTION_PASS')
for path, digest in build['retainedInputs'].items():
    assert sha(Path(path)) == digest
run_path = root / 'headless-sc-pc-headless-windowed-pc-boot-skip-result.json'
log = root / 'headless-sc-pc-headless-windowed-pc-boot-skip.log'
run = json.loads(run_path.read_text())
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and not run['logLimitReached']
assert run['skipWiiNotices'] and run['windowed'] and run['capture']
assert run['executableSha256'] == build['executableSha256'] == sha(output / 'OpenSHSMStockPCBoot')
assert run['logSha256'] == sha(log)
text = log.read_text()
assert text.count('[PCBoot] skipped console notice index=0 next=4') == 1
assert text.count('[PCBoot] skipped console notice index=5 next=6') == 1
assert '[ GPU Hang detected ]' not in text
captures = []
for bmp in sorted(root.glob('headless-sc-pc-pc-boot-skip-efb_debug_*.bmp')):
    png = bmp.with_suffix('.display.png')
    with Image.open(bmp) as image:
        rgb = image.convert('RGB')
        rgb.save(png)
        with Image.open(png) as check:
            assert check.convert('RGB').tobytes() == rgb.tobytes()
        captures.append({'bmp': str(bmp), 'bmpSha256': sha(bmp), 'png': str(png), 'pngSha256': sha(png),
            'rgbSha256': hashlib.sha256(rgb.tobytes()).hexdigest()})
assert captures
(output / 'live-audit.json').write_text(json.dumps({'result': 'PC_BOOT_OPT_IN_LIVE_RETENTION_CAPTURE_PASS',
    'runSha256': sha(run_path), 'buildSha256': sha(build_path), 'componentSha256': sha(component_path),
    'captures': captures, 'limits': ['Real boot reached both original selector boundaries, source/input/runtime retained.',
        'Sampled screenshots not every frame; screen recognition requires separate visual inspection.',
        'No full game/profile/save/controller/audio quality acceptance; release0.0.41 unchanged.']}, indent=2) + '\n')
print('PC_BOOT_OPT_IN_LIVE_RETENTION_CAPTURE_PASS', len(captures))
