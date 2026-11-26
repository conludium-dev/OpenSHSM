"""Pack a private bounded GX capture into Dolphin DFF; never game acceptance."""
from pathlib import Path
import argparse
import hashlib
import json
import struct

HEADER = struct.Struct('<III QI QI QI QI QI I QI II 8s 24s')
FRAME = struct.Struct('<QIIIQI32s')
UPDATE = struct.Struct('<IIQIB3s')
STATE_SIZES = (1024, 1024, 16384, 352, 1048576)
LIMIT = 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_fifo(data):
    offset = 0
    draws = vertices = 0
    boundaries = {0}
    cp = {}
    while offset < len(data):
        opcode = data[offset]
        if opcode == 0x61:
            size = 5
        elif opcode == 0x08:
            size = 6
            require(offset + size <= len(data), 'Truncated CP command')
            cp[data[offset + 1]] = int.from_bytes(data[offset + 2:offset + 6], 'big')
        elif opcode == 0x10:
            require(offset + 5 <= len(data), 'Truncated XF header')
            word = int.from_bytes(data[offset + 1:offset + 5], 'big')
            size = 5 + (((word >> 16) & 15) + 1) * 4
        elif opcode in (0x80, 0x88, 0x90, 0x98, 0xa0, 0xa8, 0xb0, 0xb8):
            require(offset + 3 <= len(data), 'Truncated primitive header')
            require(cp.get(0x50) == 0xabff and cp.get(0x60) == 0x5555,
                'Primitive is not direct position/NBT/colour/UV with all matrix indices')
            vat_a, vat_b, vat_c = (cp.get(i, 0) for i in (0x70, 0x80, 0x90))
            require(vat_a & 1 and (vat_a >> 1) & 7 == 4 and
                (vat_a >> 9) & 1 and (vat_a >> 10) & 7 == 4,
                'Position/NBT are not XYZ and nine F32 components')
            require((vat_a >> 14) & 7 == 5 and (vat_a >> 18) & 7 == 5,
                'Colours are not RGBA8')
            uv = [(vat_a >> 21, vat_a >> 22), (vat_b, vat_b >> 1),
                (vat_b >> 9, vat_b >> 10), (vat_b >> 18, vat_b >> 19),
                (vat_b >> 27, vat_b >> 28), (vat_c >> 5, vat_c >> 6),
                (vat_c >> 14, vat_c >> 15), (vat_c >> 23, vat_c >> 24)]
            require(all(elements & 1 and kind & 7 == 4 for elements, kind in uv),
                'Texture coordinates are not eight F32 pairs')
            count = int.from_bytes(data[offset + 1:offset + 3], 'big')
            stride = 9 + 3 * 4 + 9 * 4 + 2 * 4 + 8 * 2 * 4
            size = 3 + count * stride
            draws += 1
            vertices += count
        else:
            raise ValueError(f'Unexpected normalized FIFO opcode {opcode:#x} at {offset}')
        require(offset + size <= len(data), 'Truncated FIFO command')
        offset += size
        boundaries.add(offset)
    return boundaries, {'draws': draws, 'vertices': vertices, 'fifoBytes': len(data)}


def read_capture(path):
    require(path.stat().st_size <= LIMIT, 'Capture exceeds byte limit')
    data = path.read_bytes()
    require(data[:8] == b'OSGXCAP1', 'Invalid capture magic')
    offset = 8
    state = None
    frames = []
    current = None
    complete = False
    while offset < len(data):
        require(not complete and offset + 8 <= len(data), 'Trailing or truncated chunk')
        kind, size = struct.unpack_from('<II', data, offset)
        offset += 8
        require(offset + size <= len(data), 'Chunk outside capture')
        payload = data[offset:offset + size]
        offset += size
        if kind == 1:
            require(state is None and current is None and not frames and size == sum(STATE_SIZES), 'Invalid initial state')
            state = payload
        elif kind == 2:
            require(state is not None and current is None and len(frames) < 3, 'Unexpected FIFO chunk')
            boundaries, stats = check_fifo(payload)
            current = {'fifo': payload, 'updates': [], 'boundaries': boundaries, 'stats': stats}
        elif kind == 3:
            require(current is not None and size > 8, 'Unexpected memory chunk')
            position, address = struct.unpack_from('<II', payload)
            require(position in current['boundaries'], 'Memory update is not at a command boundary')
            require(not current['updates'] or current['updates'][-1][0] <= position, 'Unordered memory update')
            length = size - 8
            require(address + length <= 24 * 1024 * 1024 or
                0x10000000 <= address and address + length <= 0x14000000, 'Memory update outside Wii RAM')
            current['updates'].append((position, address, payload[8:]))
        elif kind == 4:
            require(current is not None and size == 4 and struct.unpack('<I', payload)[0] == len(frames), 'Invalid frame marker')
            frames.append(current)
            current = None
        elif kind == 5:
            require(current is None and size == 4 and struct.unpack('<I', payload)[0] == len(frames) == 3, 'Incomplete capture')
            complete = True
        else:
            raise ValueError(f'Unknown chunk {kind}')
    require(complete, 'Capture has no completion marker')
    return state, frames


def pack(state, frames):
    require(HEADER.size == 128 and FRAME.size == 64 and UPDATE.size == 24, 'Incorrect structure sizes')
    output = bytearray(HEADER.size + len(frames) * FRAME.size)
    offsets = []
    cursor = 0
    for size in STATE_SIZES:
        offsets.append(len(output))
        output.extend(state[cursor:cursor + size])
        cursor += size
    header = HEADER.pack(0x0d01f1f0, 6, 1, offsets[0], 256, offsets[1], 256,
        offsets[2], 4096, offsets[3], 88, HEADER.size, len(frames), 1,
        offsets[4], 1048576, 24 * 1024 * 1024, 64 * 1024 * 1024, b'R5WEA4\0\0', bytes(24))
    output[:HEADER.size] = header
    for index, frame in enumerate(frames):
        fifo_offset = len(output)
        output.extend(frame['fifo'])
        records = []
        for position, address, data in frame['updates']:
            records.append(UPDATE.pack(position, address, len(output), len(data), 1, bytes(3)))
            output.extend(data)
        updates_offset = len(output)
        output.extend(b''.join(records))
        start = HEADER.size + index * FRAME.size
        output[start:start + FRAME.size] = FRAME.pack(fifo_offset, len(frame['fifo']),
            0x00100000, 0x00110000, updates_offset, len(records), bytes(32))
    return bytes(output)


def verify(data, state, frames):
    header = HEADER.unpack_from(data)
    require(header[:3] == (0x0d01f1f0, 6, 1), 'DFF header mismatch')
    reconstructed = b''.join(data[header[i]:header[i] + size]
        for i, size in zip((3, 5, 7, 9, 14), STATE_SIZES))
    require(reconstructed == state, 'DFF state mismatch')
    require(header[12] == len(frames), 'DFF frame count mismatch')
    for index, expected in enumerate(frames):
        fifo, size, start, end, updates, count, _ = FRAME.unpack_from(data, header[11] + index * FRAME.size)
        require(start < end and count == len(expected['updates']), 'DFF frame metadata mismatch')
        require(data[fifo:fifo + size] == expected['fifo'], 'DFF FIFO mismatch')
        for i, (position, address, payload) in enumerate(expected['updates']):
            pos, addr, offset, length, kind, _ = UPDATE.unpack_from(data, updates + i * UPDATE.size)
            require((pos, addr, kind) == (position, address, 1), 'DFF update metadata mismatch')
            require(data[offset:offset + length] == payload, 'DFF resource bytes mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.with_suffix('.json').exists(), 'Output already exists')
    state, frames = read_capture(args.capture)
    data = pack(state, frames)
    verify(data, state, frames)
    with args.output.open('xb') as file:
        file.write(data)
    verify(args.output.read_bytes(), state, frames)
    report = {'result': 'DFF_CONTAINER_ROUNDTRIP_NOT_DOLPHIN_OR_GAME_VERIFIED',
        'capture': str(args.capture.resolve()), 'captureSha256': hashlib.sha256(args.capture.read_bytes()).hexdigest(),
        'output': str(args.output.resolve()), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
        'frames': [{**f['stats'], 'updates': len(f['updates']), 'resourceBytes': sum(len(u[2]) for u in f['updates'])} for f in frames],
        'limits': ['Decoded direct attributes are a diagnostic adaptation, not byte-identical original FIFO.',
            'Initial EFB pixels are absent; preceding recorded frame provides partial warmup.',
            'TLUT memory and ordered TLUT RAM loads are retained; manual TMEM preloads are refused.',
            'GPU resource sampling versus concurrent CPU writes is not synchronized beyond existing runtime behavior.',
            'Dolphin acceptance and visual equivalence must be checked separately.']}
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
