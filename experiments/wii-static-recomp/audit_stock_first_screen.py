"""Audit observed original Wii safety screen, without declaring gameplay or complete recompilation."""
from pathlib import Path
import hashlib
import json
import struct
from PIL import Image

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
game = project / 'work/private-game/disc/DATA'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
label = 'window-paced-trace-gx-windowed-loading45'
run = json.loads((root / (label + '-result.json')).read_text())
log = root / (label + '.log')
build = json.loads((root / 'window-paced/build.json').read_text())
assert run['windowed'] and run['capture'] and run['tag'] == 'loading45'
assert run['seconds'] == 45 and run['deadlineReached'] and run['terminalReturncode'] == 0
assert run['executableSha256'] == build['executableSha256']
assert sha(root / 'window-paced/OpenSHSMStockWindowPaced') == build['executableSha256']
assert sha(log) == run['logSha256']
text = log.read_text()
assert '[ GPU Hang detected ]' not in text
assert '[DI] Read: offset=0x6f6cb0e0 len=0x10800' in text
assert 'tex0=11710000/512x512/f6' in text
assert '#200001' in text and '#400001' in text
fst = (game / 'sys/fst.bin').read_bytes()
count = struct.unpack_from('>I', fst, 8)[0]
assert count * 12 <= len(fst)
strings = fst[count * 12:]
target = 0x6F6CB0E0
regions = []
for index in range(1, count):
    name_field, raw_offset, size = struct.unpack_from('>III', fst, index * 12)
    if name_field >> 24:
        continue
    name_offset = name_field & 0xFFFFFF
    name = strings[name_offset:].split(b'\0', 1)[0].decode()
    offset = raw_offset * 4
    if offset <= target and target + 0x10800 <= offset + size:
        regions.append((name, offset, size))
assert len(regions) == 1 and regions[0][0] == 'data.arc'
with (game / 'files/data.arc').open('rb') as stream:
    stream.seek(target - regions[0][1])
    chunk = stream.read(0x10800)
assert len(chunk) == 0x10800 and chunk[:2] == bytes.fromhex('78da')
dol = (game / 'sys/main.dol').read_bytes()
assert hashlib.sha256(dol).hexdigest() == run['originalDolSha256']
def instruction(address):
    for index in range(7):
        offset = struct.unpack_from('>I', dol, index * 4)[0]
        start = struct.unpack_from('>I', dol, 0x48 + index * 4)[0]
        size = struct.unpack_from('>I', dol, 0x90 + index * 4)[0]
        if start <= address and address + 4 <= start + size:
            return struct.unpack_from('>I', dol, offset + address - start)[0]
    raise AssertionError(hex(address))
assert instruction(0x802AB6C8) == 0x88030000
assert instruction(0x802AB6D8) == 0x88630003
assert instruction(0x802ACBF8) == 0x907C0000
bmp = root / 'window-paced-loading45-efb_1800.bmp'
png = bmp.with_suffix('.png')
with Image.open(bmp) as a, Image.open(png) as b:
    assert a.size == b.size == (640, 480)
    rgba = a.convert('RGBA')
    assert rgba.tobytes() == b.convert('RGBA').tobytes()
    colours = rgba.getcolors(640 * 480)
    assert colours is not None and len(colours) > 100
dimension_label = 'window-paced-trace-image-dimensions'
dimension_run = json.loads((root / (dimension_label + '-result.json')).read_text())
dimension_log = root / (dimension_label + '.log')
assert sha(dimension_log) == dimension_run['logSha256']
assert dimension_run['terminalReturncode'] == -15 and dimension_run['deadlineReached']
assert '[Peek] 902be078: 1 200 200 20 800 9055d000 0 0' in dimension_log.read_text()
(root / 'window-paced/first-screen-audit.json').write_text(json.dumps({
    'result': 'ORIGINAL_WII_SAFETY_SCREEN_OBSERVED',
    'runLogSha256': sha(log), 'captureBmpSha256': sha(bmp), 'capturePngSha256': sha(png),
    'captureRgbaSha256': hashlib.sha256(rgba.tobytes()).hexdigest(),
    'captureColours': len(colours), 'fstSha256': hashlib.sha256(fst).hexdigest(),
    'discRead': {'file': regions[0][0], 'discOffset': target,
        'fileOffset': target - regions[0][1], 'size': len(chunk),
        'compressedChunkSha256': hashlib.sha256(chunk).hexdigest()},
    'dimensionLogSha256': sha(dimension_log),
    'visualObservation': 'Nintendo Wii Remote wrist-strap/jacket safety screen, inspected from actual EFB capture.',
    'limits': ['Automated checks prove provenance/pixel consistency, not recognition; visual inspection is separate evidence.',
        'No menu/playable scene/input/controller/audio/full-game or physical Wii behavior equivalence claim.',
        'Debug unoptimized runtime:512x512 pixel conversion is slow but progresses, not an infinite wait.']
}, indent=2) + '\n')
print('PASS owned full runtime/capture/DOL/FST/data.arc provenance and live512x512 dimensions')
print('Visually observed Wii safety screen; not menu, gameplay or whole-goal completion')
