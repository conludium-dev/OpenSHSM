"""Compare captured cache pixels with an independent tiled-texture decoder."""
from pathlib import Path
import argparse
import hashlib
import json
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path)
args = parser.parse_args()
root = args.directory.resolve()
assert root.is_relative_to(Path('work/private-game/static-recomp').resolve())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
expand = lambda v, bits: (v << (8 - bits)) | (v >> (2 * bits - 8)) if bits >= 4 else (v << 5) | (v << 2) | (v >> 1)
def color(word, fmt):
    if fmt == 4:
        return (expand(word >> 11, 5), expand((word >> 5) & 63, 6), expand(word & 31, 5), 255)
    if word & 0x8000:
        return (expand((word >> 10) & 31, 5), expand((word >> 5) & 31, 5), expand(word & 31, 5), 255)
    return (expand((word >> 8) & 15, 4), expand((word >> 4) & 15, 4), expand(word & 15, 4), expand((word >> 12) & 7, 3))

def decode(raw, width, height, fmt, palette, palette_fmt):
    tiles = {0: (8, 8, 32), 1: (8, 4, 32), 2: (8, 4, 32), 3: (4, 4, 32),
        4: (4, 4, 32), 5: (4, 4, 32), 6: (4, 4, 64), 8: (8, 8, 32), 9: (8, 4, 32), 10: (4, 4, 32)}
    if fmt not in tiles:
        return None
    tw, th, tile_bytes = tiles[fmt]
    result = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            base = ((y // th) * ((width + tw - 1) // tw) + x // tw) * tile_bytes
            pixel = (y % th) * tw + x % tw
            if fmt in (0, 8):
                value = (raw[base + pixel // 2] >> (4 if pixel % 2 == 0 else 0)) & 15
            elif fmt in (1, 2, 9):
                value = raw[base + pixel]
            elif fmt != 6:
                value = int.from_bytes(raw[base + pixel * 2:base + pixel * 2 + 2], 'big')
            if fmt == 0:
                c = (value * 17,) * 4
            elif fmt == 1:
                c = (value,) * 4
            elif fmt == 2:
                c = ((value & 15) * 17,) * 3 + ((value >> 4) * 17,)
            elif fmt == 3:
                c = (value & 255,) * 3 + (value >> 8,)
            elif fmt in (4, 5):
                c = color(value, fmt)
            elif fmt == 6:
                a, r = raw[base + pixel * 2:base + pixel * 2 + 2]
                g, b = raw[base + 32 + pixel * 2:base + 34 + pixel * 2]
                c = (r, g, b, a)
            else:
                index = value & 0x3FFF
                entry = palette[index * 2:index * 2 + 2]
                assert len(entry) == 2
                if palette_fmt == 0:
                    c = (entry[1],) * 3 + (entry[0],)
                else:
                    assert palette_fmt in (1, 2)
                    c = color(int.from_bytes(entry, 'big'), 4 if palette_fmt == 1 else 5)
            position = (y * width + x) * 4
            result[position:position + 4] = bytes(c)
    return bytes(result)

records = []
for meta in sorted(root.glob('texture-*.txt'), key=lambda p: int(p.stem.split('-')[-1])):
    lines = meta.read_text().splitlines()
    assert len(lines) == 18
    seq, address, width, height, fmt, tlut, tlut_fmt, cache_hash, raw_size, stages = map(int, lines[0].split())
    bp = list(map(int, lines[1].split()))
    assert len(bp) == 256
    prefix = meta.with_suffix('')
    raw_path, rgba_path, palette_path = [prefix.with_suffix(extension) for extension in ('.raw', '.rgba', '.tlut')]
    raw, rgba, palette = raw_path.read_bytes(), rgba_path.read_bytes(), palette_path.read_bytes()
    assert len(raw) == raw_size and len(rgba) == width * height * 4
    reference = decode(raw, width, height, fmt, palette, tlut_fmt)
    mismatch = None if reference is None else sum(a != b for a, b in zip(reference, rgba))
    image_path = prefix.with_suffix('.png')
    Image.frombytes('RGBA', (width, height), rgba).save(image_path)
    alpha = rgba[3::4]
    records.append({'sequence': seq, 'address': hex(address), 'width': width, 'height': height, 'format': fmt,
        'cacheHash': cache_hash, 'independentDecodeMismatchBytes': mismatch, 'alphaRange': [min(alpha), max(alpha)],
        'cmode0': hex(bp[0x41]), 'tevStages': stages, 'tevColorEnv': [hex(bp[0xC0 + 2 * i]) for i in range(stages)],
        'tevAlphaEnv': [hex(bp[0xC1 + 2 * i]) for i in range(stages)],
        'hashes': {str(p.name): sha(p) for p in [meta, raw_path, rgba_path, palette_path, image_path]}})
(root / 'analysis.json').write_text(json.dumps({'result': 'CAPTURED_TEXTURE_COMPARISON', 'records': records,
    'verifierSha256': sha(Path(__file__)), 'sources': ['https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/VideoCommon/TextureDecoder_Generic.cpp'],
    'limits': ['Independent tile decoder for formats0..6/8..10; CMPR unverified, not all GPU formats.',
        'Same captured input, not proof input bytes/GL shader/blending/EFB aliases equal original Wii output.']}, indent=2) + '\n')
for row in records:
    print(row['sequence'], row['address'], row['width'], row['height'], 'fmt', row['format'],
        'mismatch', row['independentDecodeMismatchBytes'], 'alpha', row['alphaRange'], 'blend', row['cmode0'])
