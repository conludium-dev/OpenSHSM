"""Prepare private procedural QTE textures using the owner's supported Wii DATA tree.

Requires Python 3.11+ and Pillow. No PS2 data or developer catalogue is used.
Generated Wii-derived containers remain private and are not shipped as assets.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

from PIL import Image, ImageDraw

DOL_SHA256 = 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
UI_SHA256 = 'bef59962f492419e80df9f2c572992d4d18055fde68dabab884eef81043e12f4'


NAMES = ('PAD_CROSS', 'PAD_TRIANGLE', 'PAD_SQUARE', 'PAD_CIRCLE',
    'KEY_UP', 'KEY_DOWN', 'KEY_LEFT', 'KEY_RIGHT')
COLORS = ((100, 180, 255), (100, 245, 160), (245, 150, 225), (255, 120, 120))


def chunks(data, begin, end):
    if not 0 <= begin <= end <= len(data):
        raise ValueError('Chunk span outside input')
    position = begin
    while position < end:
        if position + 12 > end:
            raise ValueError('Truncated chunk header')
        kind, size, version = struct.unpack_from('<III', data, position)
        if position + 12 + size > end:
            raise ValueError('Chunk payload outside input')
        yield kind, version, data[position + 12:position + 12 + size]
        position += 12 + size
    assert position == end


def archive_entry(path, key):
    size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(16)
        if len(header) != 16:
            raise ValueError('Truncated archive header')
        magic, count, first, _ = struct.unpack('<4I', header)
        if magic != 0xFA10 or not 0 < count <= 100000 or not 16 + count * 16 <= first <= size:
            raise ValueError('Invalid archive header')
        table = stream.read(count * 16)
        if len(table) != count * 16:
            raise ValueError('Truncated archive table')
        selected = []
        for index in range(count):
            entry_key, offset, packed, unpacked = struct.unpack_from('<4I', table, index * 16)
            if offset < first or offset + packed > size:
                raise ValueError('Archive entry outside input')
            if entry_key == key:
                selected.append((index, offset, packed, unpacked))
        if len(selected) != 1:
            raise ValueError('Expected exactly one UI archive entry')
        index, offset, packed, unpacked = selected[0]
        if not 0 < packed <= 64 * 1024 * 1024 or unpacked > 64 * 1024 * 1024:
            raise ValueError('Unsupported UI entry size')
        stream.seek(offset)
        raw = stream.read(packed)
        if len(raw) != packed:
            raise ValueError('Truncated UI entry')
    if unpacked:
        decoder = zlib.decompressobj()
        try:
            value = decoder.decompress(raw, unpacked + 1)
        except zlib.error as error:
            raise ValueError('Invalid compressed UI entry') from error
        if len(value) != unpacked or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
            raise ValueError('Invalid compressed UI size or trailing bytes')
    else:
        value = raw
    return value, index


def texture_dictionary(leaf):
    dictionaries = []
    position = 0
    while position < len(leaf):
        if not any(leaf[position:]):
            break
        if position + 12 > len(leaf):
            raise ValueError('Truncated resource chunk')
        kind, size, _ = struct.unpack_from('<III', leaf, position)
        inner = position + 12
        end = inner + size
        if not size or end > len(leaf):
            raise ValueError('Resource chunk outside UI entry')
        if kind == 0x716:
            if size < 8:
                raise ValueError('Truncated resource header')
            header, tag = struct.unpack_from('>II', leaf, inner)
            guid = inner + 8 + tag
            if tag > 1024 or guid + 20 > end:
                raise ValueError('Invalid resource name span')
            length = struct.unpack_from('>I', leaf, guid + 16)[0]
            payload = inner + 4 + header
            if length > 256 or guid + 20 + length > end or payload < guid + 20 + length or payload + 4 > end:
                raise ValueError('Invalid resource type/payload span')
            count = struct.unpack_from('>I', leaf, payload)[0]
            if payload + 4 + count > end:
                raise ValueError('Resource payload outside chunk')
            resource_type = leaf[guid + 20:guid + 20 + length]
            label, separator, _ = resource_type.partition(b'\0')
            if not separator or any(byte < 32 or byte > 126 for byte in label):
                raise ValueError('Invalid resource type')
            if label == b'rwID_TEXDICTIONARY':
                dictionaries.append(leaf[payload + 4:payload + 4 + count])
        position = end
    if len(dictionaries) != 1:
        raise ValueError('Expected exactly one UI texture dictionary')
    return dictionaries[0]


def chunk(kind, version, payload):
    return struct.pack('<III', kind, len(payload), version) + payload


def glyph(index):
    scale = 4
    image = Image.new('L', (32 * scale, 32 * scale), 0)
    draw = ImageDraw.Draw(image)
    point = lambda x, y: (x * scale, y * scale)
    if index == 0:
        draw.line([point(9, 9), point(23, 23)], fill=255, width=3 * scale)
        draw.line([point(23, 9), point(9, 23)], fill=255, width=3 * scale)
    elif index == 1:
        draw.line([point(16, 6), point(27, 25), point(5, 25), point(16, 6)], fill=255, width=2 * scale)
    elif index == 2:
        draw.rectangle([point(7, 7), point(25, 25)], outline=255, width=2 * scale)
    elif index == 3:
        draw.ellipse([point(6, 6), point(26, 26)], outline=255, width=2 * scale)
    else:
        draw.rounded_rectangle([point(3, 3), point(29, 29)], radius=4 * scale, outline=255, width=scale)
        arrow = Image.new('L', image.size, 0)
        arrow_draw = ImageDraw.Draw(arrow)
        arrow_draw.polygon([point(16, 8), point(8, 17), point(13, 17), point(13, 24),
            point(19, 24), point(19, 17), point(24, 17)], fill=255)
        angles = (0, 180, 90, -90)
        image = Image.frombytes('L', image.size, bytes(max(a, b) for a, b in
            zip(image.tobytes(), arrow.rotate(angles[index - 4]).tobytes())))
    alpha = image.resize((32, 32), Image.Resampling.LANCZOS)
    levels = [min(7, (value * 7 + 127) // 255) for value in alpha.tobytes()]
    color = COLORS[index] if index < 4 else (255, 255, 255)
    palette = []
    for level in range(16):
        if level == 0 or level > 7:
            word = 0
        elif level == 7:
            word = 0x8000 | (color[0] * 31 // 255) << 10 | (color[1] * 31 // 255) << 5 | color[2] * 31 // 255
        else:
            word = level << 12 | (color[0] // 17) << 8 | (color[1] // 17) << 4 | color[2] // 17
        palette.append(word)
    pixels = bytearray()
    for ty in range(0, 32, 8):
        for tx in range(0, 32, 8):
            for y in range(8):
                for x in range(0, 8, 2):
                    pixels.append(levels[(ty + y) * 32 + tx + x] << 4 | levels[(ty + y) * 32 + tx + x + 1])
    return palette, bytes(pixels), levels


def decode(palette, pixels):
    rgba = bytearray(32 * 32 * 4)
    position = 0
    for ty in range(0, 32, 8):
        for tx in range(0, 32, 8):
            for y in range(8):
                for x in range(0, 8, 2):
                    value = pixels[position]
                    position += 1
                    for step, entry in enumerate((value >> 4, value & 15)):
                        word = palette[entry]
                        if word & 0x8000:
                            color = ((word >> 10 & 31) * 255 // 31, (word >> 5 & 31) * 255 // 31,
                                (word & 31) * 255 // 31, 255)
                        else:
                            color = ((word >> 8 & 15) * 17, (word >> 4 & 15) * 17,
                                (word & 15) * 17, (word >> 12 & 7) * 255 // 7)
                        at = ((ty + y) * 32 + tx + x + step) * 4
                        rgba[at:at + 4] = bytes(color)
    assert position == len(pixels)
    return bytes(rgba)


def main(args, emit_result=True):
    args.game_data = args.game_data.resolve(strict=True)
    output = args.output.absolute()
    resolved_output = output.resolve()
    if resolved_output == args.game_data or args.game_data in resolved_output.parents:
        raise ValueError('Output must be outside the original DATA tree')
    boot = (args.game_data / 'sys/boot.bin').read_bytes()
    if len(boot) < 8 or boot[:6] != b'R5WEA4' or boot[7] != 0:
        raise ValueError('Only Wii US R5WEA4 rev0 is verified')
    dol_sha = hashlib.sha256((args.game_data / 'sys/main.dol').read_bytes()).hexdigest()
    if dol_sha != DOL_SHA256:
        raise ValueError('Unsupported Wii DOL')
    leaf, leaf_index = archive_entry(args.game_data / 'files/data.arc', 0xF7C)
    leaf_sha = hashlib.sha256(leaf).hexdigest()
    if leaf_sha != UI_SHA256:
        raise ValueError('Unsupported Wii UI resource')
    dictionary = texture_dictionary(leaf)
    [(kind, version, body)] = list(chunks(dictionary, 0, len(dictionary)))
    assert kind == 0x16
    template = None
    dictionary_struct = None
    for kind, version, payload in chunks(body, 0, len(body)):
        if kind == 1:
            dictionary_struct = payload
        if kind != 0x15:
            continue
        entries = list(chunks(payload, 0, len(payload)))
        header = entries[0][2]
        if header[0x18:0x38].split(b'\0')[0] == b'UI_HourglassIcon':
            template = entries
    assert template is not None and dictionary_struct is not None
    header = template[0][2]
    assert len(header) == 652 and int.from_bytes(header[:4], 'big') == 6
    assert struct.unpack_from('>HH', header, 0x5C) == (32, 32)
    assert header[0x61:0x64] == bytes((1, 8, 2))
    assert int.from_bytes(header[0x88:0x8C], 'big') == 512
    output.mkdir(exist_ok=False)
    texture_chunks = []
    records = []
    contact = Image.new('RGBA', (32 * 4, 32 * 2), (20, 24, 28, 255))
    for index, suffix in enumerate(NAMES):
        name = 'OpenSHSM_QTE_' + suffix
        palette, pixels, levels = glyph(index)
        payload = bytearray(header)
        payload[0x18:0x38] = name.encode().ljust(32, b'\0')
        payload[0x68:0x88] = struct.pack('>16H', *palette)
        payload[0x8C:] = pixels
        assert len(payload) == len(header)
        entries = [chunk(kind, version, bytes(payload) if i == 0 else data)
            for i, (kind, version, data) in enumerate(template)]
        texture_chunks.append(chunk(0x15, template[0][1], b''.join(entries)))
        rgba = decode(palette, pixels)
        assert all(rgba[i * 4 + 3] == (255 if level == 7 else level * 255 // 7) for i, level in enumerate(levels))
        image = Image.frombytes('RGBA', (32, 32), rgba)
        image.save(output / (name + '.png'))
        contact.alpha_composite(image, (index % 4 * 32, index // 4 * 32))
        records.append({'name': name, 'width': 32, 'height': 32, 'format': 'GX_C4_RGB5A3',
            'rgbaSha256': hashlib.sha256(rgba).hexdigest(), 'pixelSha256': hashlib.sha256(pixels).hexdigest()})
    struct_payload = struct.pack('<H', len(texture_chunks)) + dictionary_struct[2:]
    body = chunk(1, template[0][1], struct_payload) + b''.join(texture_chunks) + chunk(3, template[0][1], b'')
    result = chunk(0x16, template[0][1], body)
    (output / 'qte-glyphs.txd').write_bytes(result)
    contact.resize((512, 256), Image.Resampling.NEAREST).save(output / 'preview.png')
    report = {'result': 'OWN_WII_DERIVED_QTE_GLYPHS_ENCODED_NOT_NATIVE_ACCEPTED',
        'dolSha256': dol_sha, 'leaf': leaf_index, 'leafSha256': leaf_sha, 'template': 'UI_HourglassIcon',
        'templateSha256': hashlib.sha256(header).hexdigest(), 'textureCount': len(records), 'textures': records,
        'txdSha256': hashlib.sha256(result).hexdigest(), 'txdBytes': len(result),
        'ps2AssetsUsed': False, 'gameplayAccepted': False,
        'limits': ['Private TXD derives native metadata from the own Wii copy; do not publish it.',
            'Writer/decoder round trip only. Original native loader and visible UI still need verification.']}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    if emit_result:
        print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    try:
        main(parser.parse_args())
    except (OSError, ValueError, AssertionError, struct.error) as error:
        parser.exit(1, 'OpenSHSM QTE preparation: ' + str(error) + '\n')
