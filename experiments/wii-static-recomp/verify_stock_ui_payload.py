"""Identify the live loading payload by exact bytes from the owned Wii archive, not size alone."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import runpy
import struct
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--tag', default='payload60')
args = parser.parse_args()
if not Path('outputs/shsm-research/native').exists():
    raise SystemExit('Historical UI-layout probe depends on the retired native implementation. Existing evidence remains historical; this is not a current recompilation acceptance check.')
assert re.fullmatch('[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-loading-payload'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
extractor_path = Path('outputs/shsm-research/verification/extract-phone-layouts.py')
reader = runpy.run_path(str(extractor_path))
key = reader['filename_hash']('UI.arc')
assert key == 0x181DFBA2 and b'UI.arc\0' in dol.read_bytes()
archive = Path('work/private-game/disc/DATA/files/igc.arc')
with archive.open('rb') as file:
    header = file.read(16)
    count = struct.unpack('<4I', header)[1]
    assert struct.unpack('<4I', header)[0] == 0xFA10 and count == 289
    table = file.read(count * 16)
    candidates = [(i, struct.unpack_from('<4I', table, i * 16)) for i in range(count)
        if struct.unpack_from('<I', table, i * 16)[0] == key]
    assert len(candidates) == 1 and candidates[0][0] == 9
    _, offset, packed, unpacked = candidates[0][1]
    assert unpacked == 0 and offset + packed <= archive.stat().st_size
    file.seek(offset)
    original = file.read(packed)
prefix = root / ('window-loading-payload-' + args.tag + '-thp')
metadata_path = Path(str(prefix) + '-payloads.jsonl')
metadata = [json.loads(line) for line in metadata_path.read_text().splitlines()]
selected = next(row for row in metadata if row['id'] == 9)
capture_path = Path(str(prefix) + '-payload9.bin')
captured = capture_path.read_bytes()
assert len(captured) == selected['size'] == 661504
position = captured.find(original)
names = {reader['filename_hash'](name + '.xaml'): name for name in reader['NAMES']}
names.update({value: name for name, value in reader['FRONT_END_KEYS'].items()})
nested = list(reader['entries'](original))
files = []
scan_path = Path(str(prefix) + '-scan.jsonl')
scan_rows = [json.loads(line) for line in scan_path.read_text().splitlines()] if scan_path.exists() else []
string_matches = {row['index']: [] for row in scan_rows}
for index, entry in enumerate(nested):
    value = reader['payload'](original, entry)
    fbxf = value[8:12] == b'FBXF'
    if fbxf:
        string_offset = struct.unpack_from('<I', value, 16)[0]
        assert 20 <= string_offset <= len(value)
        root_pointer = struct.unpack_from('<I', value, 4)[0]
        assert string_offset <= root_pointer < len(value)
        root_type = value[root_pointer:].split(b'\0', 1)[0].decode('ascii')
        strings = set(value[string_offset:].split(b'\0'))
        for row in scan_rows:
            if bytes.fromhex(row['inputHex']) in strings:
                string_matches[row['index']].append({'index': index, 'key': f'{entry[0]:08X}', 'knownName': names.get(entry[0])})
    files.append({'index': index, 'key': f'{entry[0]:08X}', 'knownName': names.get(entry[0]),
        'size': len(value), 'fbxf': fbxf, 'rootType': root_type if fbxf else None, 'sha256': hashlib.sha256(value).hexdigest()})
subtitle_bytes = reader['payload'](original, nested[96])
assert files[96]['rootType'] == 'Subtitles'
subtitles_path = output / 'wii-subtitles-from-uiarc.fbxf'
if subtitles_path.exists():
    assert subtitles_path.read_bytes() == subtitle_bytes
else:
    subtitles_path.write_bytes(subtitle_bytes)
assert sha(subtitles_path) == files[96]['sha256']
prepared_path = Path('work/private-game/player-research/prepared-original-menu-current/phone/wii-subtitles.fbxf')
prepared_match = sha(prepared_path) == files[96]['sha256'] if prepared_path.exists() else None
source = Path('experiments/wii-static-recomp/stock_subtitle_layout_probe.cpp')
exe = output / 'subtitle-layout-probe'
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
    '-I', str(Path('outputs/shsm-research/native').resolve()), str(source.resolve()), '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=30)
(output / 'subtitle-layout-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
values = [bytes.fromhex(row['inputHex']).decode('ascii') for row in scan_rows if bytes.fromhex(row['formatHex']) == b'%f,%f']
result = subprocess.run([str(exe.resolve()), str(subtitles_path.resolve()), *values], capture_output=True, text=True, timeout=10)
(output / 'subtitle-layout.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
report = {'result': 'LIVE_UI_ARC_EXACT_SOURCE_MATCH' if position >= 0 else 'UI_ARC_LIVE_BYTES_NOT_MATCHED',
    'archive': 'igc.arc', 'outerIndex': 9, 'key': f'{key:08X}', 'filename': 'UI.arc',
    'outerOffset': offset, 'packedBytes': packed, 'liveBytes': len(captured), 'sourceMatchOffset': position,
    'extraBytes': len(captured) - len(original), 'nestedEntries': len(nested), 'files': files,
    'originalDolSha256': sha(dol), 'originalTableSha256': hashlib.sha256(table).hexdigest(),
    'originalPayloadSha256': hashlib.sha256(original).hexdigest(), 'captureSha256': sha(capture_path),
    'metadataSha256': sha(metadata_path), 'extractorSha256': sha(extractor_path), 'scriptSha256': sha(Path(__file__)),
    'scanCaptureSha256': sha(scan_path) if scan_path.exists() else None,
    'scanStringMatches': [{'scanIndex': row['index'], 'input': bytes.fromhex(row['inputHex']).decode('ascii'),
        'matches': string_matches[row['index']]} for row in scan_rows],
    'subtitleProbe': {'sourceSha256': sha(source), 'executableSha256': sha(exe), 'layoutSha256': sha(subtitles_path),
        'existingPreparedLayoutMatch': prepared_match,
        'headerHashes': {name: sha(Path('outputs/shsm-research/native') / name) for name in ('PhoneLayout.h', 'PhoneNavigation.h')},
        'command': command, 'output': result.stdout, 'logSha256': sha(output / 'subtitle-layout.log')},
    'limits': ['Exact packed resource match identifies source, not parser/constructor/graphics correctness.',
        'Extra live bytes are captured buffer slack/header candidate; exact origin is not asserted.',
        'Nested keys use existing verified Wii extractor aliases; no original assets copied into public files.',
        'Exact string-table matches identify candidate layouts, not active parser cursor or completed object construction.']}
(output / ('ui-source-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], 'source offset', position, 'extra bytes', report['extraBytes'], 'nested', len(nested))
assert position >= 0
