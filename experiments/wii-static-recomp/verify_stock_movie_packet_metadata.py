"""Verify actual Wii caller metadata and identify captured packet content, preserving repeated-frame ambiguity."""
from pathlib import Path
import hashlib
import json
import re
import struct

project = Path('.').resolve()
private = project / 'work/private-game/static-recomp'
root = private / 'stock-baseline'
output = root / 'movie-packet-metadata'
output.mkdir(exist_ok=True)
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

dol_path = project / 'work/private-game/disc/DATA/sys/main.dol'
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
asm_path = private / 'dtk-output/asm/auto_03_800999A8_text.s'
assembly = asm_path.read_text()
words = {int(address, 16): bytes.fromhex(word) for address, word in re.findall(
    r'/\* ([0-9A-F]{8}) [0-9A-F]{8}  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/', assembly)}
source_path = root / 'window-cpu-time/output_11.cpp'
source = source_path.read_text()
checked = []
for address in range(0x8009C55C, 0x8009C678, 4):
    section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    offset = layout[section] + address - layout[18 + section]
    word = dol[offset:offset + 4]
    assert words[address] == word
    marker = f'// 0x{address:08X}: {word.hex().upper()}'
    assert source.count(marker) == 1
    checked.append({'address': address, 'word': word.hex()})
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
proof_path = root / 'headless-thp-snapshot/replay/verification.json'
proof = json.loads(proof_path.read_text())
assert sha(snapshot) == proof['snapshotSha256']
context_path = root / 'window-quantization/include/runtime/cpu_context.h'
context_source = context_path.read_text()
for allocation in ['mem1.resize(24 * 1024 * 1024 + 8, 0);', 'mem2.resize(64 * 1024 * 1024 + 8, 0);',
    'locked_cache.resize(256 * 1024 + 8, 0);']:
    assert allocation in context_source
with snapshot.open('rb') as stream:
    registers = stream.read(784)
    assert registers[:8] == b'SHSMFP01'
    gpr = struct.unpack_from('<32I', registers, 8)
    pc, lr = struct.unpack_from('<2I', registers, 728)
    assert pc == 0x80209D80 and lr == 0x8009C5E4
    banks = []
    for base, expected in [(0x80000000, 24 * 1024 * 1024), (0x90000000, 64 * 1024 * 1024),
        (0xE0000000, 256 * 1024)]:
        size = struct.unpack('<Q', stream.read(8))[0]
        assert size == expected + 8
        banks.append((base, expected, stream.tell()))
        stream.seek(size, 1)
    assert stream.tell() == snapshot.stat().st_size

def read_ram(address, size):
    if not isinstance(size, int) or size < 1 or size > 1024 * 1024 or address < 0 or address + size > 0x100000000:
        raise ValueError('Invalid observer range')
    bank = next((row for row in banks if row[0] <= address and address + size <= row[0] + row[1]), None)
    if bank is None:
        raise ValueError('Not one contiguous captured RAM bank')
    with snapshot.open('rb') as stream:
        stream.seek(bank[2] + address - bank[0])
        data = stream.read(size)
    if len(data) != size:
        raise ValueError('Truncated RAM')
    return data

read32 = lambda address: int.from_bytes(read_ram(address, 4), 'big')
count = read32(gpr[30] + 0x6C)
index = gpr[26]
assert 0 < count <= 16 and index < count
frame_base = read32(gpr[23])
sizes = [read32(frame_base + 8 + 4 * i) for i in range(count)]
size_slot = frame_base + 8 + 4 * index
packet_address = frame_base + 8 + 4 * count + sum(sizes[:index])
assert gpr[25] == size_slot and gpr[24] == gpr[3] == packet_address
assert gpr[28] == gpr[30] + index and read_ram(gpr[28] + 0x70, 1) == b'\0'
packet = read_ram(packet_address, sizes[index])
assert packet[:2] == b'\xFF\xD8'
packet_sha = hashlib.sha256(packet).hexdigest()
matches, sources = [], []
for movie in sorted((project / 'work/private-game/disc/DATA/files/MOVIES').iterdir()):
    if not movie.is_file():
        continue
    with movie.open('rb') as stream:
        header = stream.read(48)
        if header[:4] != b'THP\0':
            continue
        word = lambda offset: int.from_bytes(header[offset:offset + 4], 'big')
        stream.seek(word(0x20))
        components = stream.read(20)
        component_count = int.from_bytes(components[:4], 'big')
        assert 0 < component_count <= 16
        video_indices = [i for i in range(component_count) if components[4 + i] == 0]
        offset, size = word(0x28), word(0x18)
        movie_size = movie.stat().st_size
        for frame in range(word(0x14)):
            assert size >= 8 + 4 * component_count and offset + size <= movie_size
            stream.seek(offset)
            frame_header = stream.read(8 + 4 * component_count)
            lengths = [int.from_bytes(frame_header[8 + 4 * i:12 + 4 * i], 'big') for i in range(component_count)]
            assert sum(lengths) <= size - len(frame_header)
            for component_index in video_indices:
                if lengths[component_index] == len(packet):
                    stream.seek(offset + len(frame_header) + sum(lengths[:component_index]))
                    if stream.read(lengths[component_index]) == packet:
                        matches.append({'movie': movie.name, 'frame': frame, 'component': component_index})
            following = int.from_bytes(frame_header[:4], 'big')
            offset += size
            size = following
    sources.append({'path': str(movie), 'sha256': sha(movie)})
assert matches
refusals = []
for name, address, size in [('zero', packet_address, 0), ('negative', packet_address, -1),
    ('oversized', packet_address, 1024 * 1024 + 1), ('wrap', 0xFFFFFFFE, 8),
    ('unmapped', 0xCC000000, 4), ('bank-crossing', 0x93FFFFFE, 8)]:
    try:
        read_ram(address, size)
    except ValueError:
        refusals.append(name)
    else:
        raise AssertionError(name)
(output / 'verification.json').write_text(json.dumps({
    'result': 'OWN_WII_CALLER_PACKET_METADATA_BYTES_IDENTIFIED',
    'verifierSha256': sha(Path(__file__)), 'originalDolSha256': sha(dol_path),
    'dtkAssemblySha256': sha(asm_path), 'generatedSourceSha256': sha(source_path),
    'snapshotSha256': sha(snapshot), 'snapshotProofSha256': sha(proof_path), 'checkedWords': checked,
    'snapshotContextHeaderSha256': sha(context_path), 'capturedLogicalBanks': banks,
    'componentCount': count, 'componentIndex': index, 'frameBase': frame_base,
    'sizeSlot': size_slot, 'packetAddress': packet_address, 'packetBytes': len(packet),
    'packetSha256': packet_sha, 'matchingOriginalFrames': matches, 'movieSources': sources,
    'rangeRefusals': refusals,
    'facts': {'original': ['Caller computes data start from frame+8+4*componentCount.',
        'r25 points at current size word, r24/r3 at current payload; loop advances by the current length.',
        'Video component dispatch tests type byte0; snapshot matches original metadata and exact owned bytes.'],
        'inferred': ['Identical packet content may belong to multiple frame indices; preserve all matches.'],
        'pcAdaptation': ['Read-only captured-bank reader and offline exact-content identification; not guest runtime.']},
    'limits': ['71 original instruction words match DOL/DTK/generated markers; not independent execution of the whole caller.',
        'One original native decoder-entry snapshot, not physical Wii save state or all live frame metadata.',
        'No new runtime observer, speed/FPS/audio/profile/save/controller proof; old timing logs lack packet bytes.']}, indent=2) + '\n')
print('OWN_WII_CALLER_PACKET_METADATA_BYTES_IDENTIFIED', count, index, len(packet), matches)
