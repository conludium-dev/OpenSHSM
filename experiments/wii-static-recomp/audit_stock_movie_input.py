"""Bind actual caller captures to decoder intervals and exact owned THP content, retaining duplicate matches."""
from pathlib import Path
import hashlib
import json
import statistics
import struct

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
output = root / 'window-movie-input'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
for unit, change in build['changes'].items():
    assert (output / f'output_{unit}.cpp').read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(output / f'output_{unit}.cpp.o') == change['objectSha256']
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['result'] == 'ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3'
assert component['buildSha256'] == sha(build_path)
cap_path = root / 'movie-packet-metadata/aggregate-cap-verification.json'
cap = json.loads(cap_path.read_text())
assert cap['result'] == 'MOVIE_INPUT_AGGREGATE_16MIB_CAP_PASS' and cap['buildSha256'] == sha(build_path)
run_path = root / 'headless-sc-pc-headless-windowed-movie-input-result.json'
run = json.loads(run_path.read_text())
assert run['executableSha256'] == sha(output / 'OpenSHSMStockMovieInput') == build['executableSha256']
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and not run['logLimitReached']
assert all(run[key] for key in ('windowed', 'movieTiming', 'wallTimebase', 'dspSupply'))
assert sha(root / 'headless-sc-pc-headless-windowed-movie-input.log') == run['logSha256']
timing_path = root / 'headless-sc-pc-movie-input-movie-timing.jsonl'
metadata_path = Path(str(timing_path) + '.inputs.jsonl')
data_path = Path(str(timing_path) + '.inputs.bin')
timing = [json.loads(line) for line in timing_path.read_text().splitlines()]
metadata = [json.loads(line) for line in metadata_path.read_text().splitlines()]
data = data_path.read_bytes()
assert 0 < len(metadata) <= 128 and len(data) <= 16 * 1024 * 1024
assert all(row['serial'] == index for index, row in enumerate(timing))
captured = {}
offset = 0
for index, row in enumerate(metadata):
    assert row['index'] == index and row['offset'] == offset and 2 <= row['bytes'] <= 1024 * 1024
    packet = data[offset:offset + row['bytes']]
    assert len(packet) == row['bytes'] and packet[:2] == b'\xff\xd8'
    digest = hashlib.sha256(packet).hexdigest()
    captured.setdefault((len(packet), digest), packet)
    row['packetSha256'] = digest
    offset += row['bytes']
assert offset == len(data)
matches = {key: [] for key in captured}
sources = []
movie_info = {}
for movie in sorted((project / 'work/private-game/disc/DATA/files/MOVIES').iterdir()):
    if not movie.is_file():
        continue
    with movie.open('rb') as stream:
        header = stream.read(48)
        if header[:4] != b'THP\0':
            continue
        word = lambda offset: int.from_bytes(header[offset:offset + 4], 'big')
        movie_info[movie.name] = {'frames': word(0x14), 'fps': struct.unpack_from('>f', header, 0x10)[0]}
        stream.seek(word(0x20))
        components = stream.read(20)
        count = int.from_bytes(components[:4], 'big')
        assert 0 < count <= 16
        video_indices = [i for i in range(count) if components[4 + i] == 0]
        offset, size = word(0x28), word(0x18)
        movie_size = movie.stat().st_size
        for frame in range(word(0x14)):
            assert size >= 8 + 4 * count and offset + size <= movie_size
            stream.seek(offset)
            frame_header = stream.read(8 + 4 * count)
            lengths = [int.from_bytes(frame_header[8 + 4 * i:12 + 4 * i], 'big') for i in range(count)]
            assert sum(lengths) <= size - len(frame_header)
            for i in video_indices:
                if lengths[i] not in {key[0] for key in captured}:
                    continue
                stream.seek(offset + len(frame_header) + sum(lengths[:i]))
                packet = stream.read(lengths[i])
                key = (len(packet), hashlib.sha256(packet).hexdigest())
                if key in captured:
                    assert packet == captured[key]
                    matches[key].append({'movie': movie.name, 'frame': frame, 'component': i})
            following = int.from_bytes(frame_header[:4], 'big')
            offset += size
            size = following
    sources.append({'path': str(movie), 'sha256': sha(movie)})
pending, completed, displaced, unpaired = {}, {}, [], []
for row in timing:
    if row['site'] not in (0x80209D80, 0x8020A044):
        continue
    key = (row['thread'], row['sp'])
    if row['site'] == 0x80209D80:
        if key in pending:
            displaced.append(pending[key])
        pending[key] = row
    else:
        begin = pending.pop(key, None)
        if begin is None or begin['lr'] != row['lr']:
            unpaired.append(row)
            continue
        completed[begin['serial']] = row
records = []
for row in metadata:
    caller = timing[row['serial']]
    assert caller['site'] == 0x8009C5E0 and caller['r3'] == row['input']
    assert caller['thread'] == row['thread'] and caller['sp'] == row['sp']
    begin = timing[row['serial'] + 1]
    assert begin['site'] == 0x80209D80 and begin['r3'] == row['input'] and begin['lr'] == 0x8009C5E4
    assert begin['thread'] == row['thread'] and begin['sp'] == row['sp']
    found = matches[(row['bytes'], row['packetSha256'])]
    assert found
    position_matches = [match for match in found if match['frame'] == row['descriptorField4'] and match['component'] == row['component']]
    end = completed.get(begin['serial'])
    records.append({'capture': row, 'matchingOriginalFrames': found, 'rawPositionMatches': position_matches,
        'begin': begin, 'end': end, 'wallUs': end['hostUs'] - begin['hostUs'] if end else None,
        'hostCpuUs': end['hostThreadCpuUs'] - begin['hostThreadCpuUs'] if end else None})
complete = [row for row in records if row['end']]
assert complete
assert [row['serial'] for row in timing if row['site'] == 0x8009C5E0][:len(metadata)] == [row['serial'] for row in metadata]
groups = {}
for record in records:
    normalized = [match for match in record['matchingOriginalFrames']
        if match['frame'] == record['capture']['descriptorField4'] % movie_info[match['movie']]['frames']
        and match['component'] == record['capture']['component']]
    record['moduloPositionMatches'] = normalized
    if len(normalized) == 1:
        groups.setdefault(normalized[0]['movie'], []).append(record)
playback = {}
for movie, group in groups.items():
    elapsed = group[-1]['begin']['hostUs'] - group[0]['begin']['hostUs']
    steps = [b['capture']['descriptorField4'] - a['capture']['descriptorField4'] for a, b in zip(group, group[1:])]
    playback[movie] = {'capturedStarts': len(group), 'headerFps': movie_info[movie]['fps'],
        'originalFrames': movie_info[movie]['frames'], 'elapsedBetweenStartsUs': elapsed,
        'decoderStartsPerWallSecond': (len(group) - 1) * 1000000 / elapsed if elapsed else None,
        'medianPositionStep': statistics.median(steps) if steps else None,
        'stepsGreaterThanOne': sum(step > 1 for step in steps),
        'medianCompletedWallUs': statistics.median(row['wallUs'] for row in group if row['end'])}
summary = {'capturedPackets': len(records), 'captureBytes': len(data), 'uniqueContents': len(captured),
    'completeCapturedDecoderIntervals': len(complete),
    'ambiguousContentRecords': sum(len(row['matchingOriginalFrames']) > 1 for row in records),
    'rawPositionIdentifiesOneMatch': sum(len(row['rawPositionMatches']) == 1 for row in records),
    'moduloPositionIdentifiesOneMatch': sum(len(row['moduloPositionMatches']) == 1 for row in records),
    'medianCapturedWallUs': statistics.median(row['wallUs'] for row in complete),
    'returnValues': sorted(set(row['end']['r3'] for row in complete)),
    'movies': sorted({match['movie'] for row in records for match in row['matchingOriginalFrames']}),
    'capturedPlayback': playback}
(output / 'live-input-audit.json').write_text(json.dumps({
    'result': 'LIVE_CALLER_PACKETS_EXACT_OWNED_CONTENT_INTERVALS_AUDITED',
    'buildSha256': sha(build_path), 'componentSha256': sha(component_path), 'capSha256': sha(cap_path),
    'runSha256': sha(run_path), 'timingSha256': sha(timing_path), 'metadataSha256': sha(metadata_path),
    'dataSha256': sha(data_path), 'auditorSha256': sha(Path(__file__)), 'movieSources': sources,
    'summary': summary, 'records': records, 'displaced': displaced, 'unpaired': unpaired,
    'pending': list(pending.values()),
    'limits': ['Exact packet bytes match owned THP resources; all duplicate-content matches retained.',
        'Raw descriptorField4 correspondence empirical for captured packets, not all-region original field-name proof.',
        'Modulo position is supported by captured exact content/header lengths; original looping counter logic not executed separately.',
        'Decoder starts are not GPU presentation/display FPS; position gaps are observed, not all-stage drop attribution.',
        'Observer file IO changes scheduling/cache; no controlled speedup versus earlier noncapturing runs.',
        'Decoder host-thread interval includes other guest/IRQ work; not pure codec CPU or physical Wii behavior.',
        '128packet cap covers startup prefix only, not full animated menu/story/audio/profile/save/controller fidelity.']}, indent=2) + '\n')
print('LIVE_CALLER_PACKETS_EXACT_OWNED_CONTENT_INTERVALS_AUDITED')
print(json.dumps(summary, indent=2))
