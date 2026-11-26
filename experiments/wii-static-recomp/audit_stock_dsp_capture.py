"""Freeze bounded live DSP evidence and identify the embedded DOL firmware candidate."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import tempfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize_audio_callbacks(texts):
    samples = {}
    for text in texts:
        for line in text.splitlines():
            if not line.startswith('[AudioCallback] '):
                continue
            row = {key: int(value) for key, value in re.findall(r'(\w+)=(\d+)', line)}
            if set(row) != {'wallUs', 'calls', 'requested', 'supplied', 'missing', 'short', 'errors', 'final'}:
                raise ValueError('Incomplete audio callback record')
            if row['requested'] != row['supplied'] + row['missing'] or row['short'] > row['calls']:
                raise ValueError('Invalid audio callback accounting')
            if row['wallUs'] in samples and samples[row['wallUs']] != row:
                raise ValueError('Conflicting duplicate audio callback record')
            samples[row['wallUs']] = row
    ordered = [samples[key] for key in sorted(samples)]
    if not ordered or ordered[-1]['final'] != 1:
        raise ValueError('Closed run requires final audio callback record')
    intervals = []
    for before, after in zip(ordered, ordered[1:]):
        delta = {key: after[key] - before[key] for key in ('wallUs', 'calls', 'requested', 'supplied', 'missing', 'short', 'errors')}
        if any(value < 0 for value in delta.values()) or before['final']:
            raise ValueError('Nonmonotonic audio callback accounting')
        intervals.append({'startUs': before['wallUs'], 'endUs': after['wallUs'], **delta})
    final = ordered[-1]
    return {'samples': len(ordered), 'first': ordered[0], 'final': final,
        'missingRequestedFraction': final['missing'] / final['requested'] if final['requested'] else 0,
        'intervalsWithShortage': sum(row['missing'] > 0 for row in intervals),
        'largestObservedGapUs': max((row['wallUs'] for row in intervals), default=0),
        'lastObservedShortage': next((row for row in reversed(intervals) if row['missing']), None),
        'lastInterval': intervals[-1] if intervals else None,
        'limits': ['Cumulative callback accounting, not PCM content, DSP correctness or listening acceptance.',
            'Prefix/tail logs may have gaps; interval deltas describe the entire gap, not a continuous per-second trace.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--play', type=Path, required=True)
    args = parser.parse_args()
    play_path = args.play.resolve()
    assert play_path.parent == Path('/private/tmp') and play_path.name.startswith('openshsm-pc-play-')
    record_path = play_path / 'result.json'
    record = json.loads(record_path.read_text())
    build_path = Path(record['dspCaptureBuildPath'])
    assert sha(build_path) == record['dspCaptureBuildSha256']
    build = json.loads(build_path.read_text())
    assert build['result'] == 'BOUNDED_DSP_CAPTURE_CURRENT_RUNTIME_COMPONENT_PASS_NOT_LIVE_VERIFIED'
    assert sha(build['executablePath']) == build['executableSha256']
    font_path = Path(record['fontBuildPath']) if record.get('fontBuildPath') else None
    ax_path = Path(record['axBuildPath']) if record.get('axBuildPath') else None
    if font_path:
        assert sha(font_path) == record['fontBuildSha256']
        from stock_debug_font_build import validate as validate_font
        executable = validate_font(font_path, build_path, build)
        if ax_path:
            assert sha(ax_path) == record['axBuildSha256']
            from stock_axwii_device_build import validate as validate_ax
            executable = validate_ax(ax_path, font_path, json.loads(font_path.read_text()), build_path)
        assert sha(executable) == record['executableSha256']
    else:
        assert not ax_path, 'AX capture requires its verified font/DSP parent chain.'
        assert record['executableSha256'] == build['executableSha256']
    directory = play_path / 'private-dsp-capture'
    metadata = directory / 'dsp-events.jsonl'
    raw = metadata.read_bytes()
    complete = raw[:raw.rfind(b'\n') + 1]
    rows = [json.loads(line) for line in complete.splitlines()]
    mails = [row for row in rows if row['kind'] == 'mail']
    lists = [row for row in rows if row['kind'] == 'list']
    dma = [row for row in rows if row['kind'] == 'dma-to-aram']
    firmware_rows = [row for row in rows if row['kind'] == 'firmware-ram-candidate']
    pbs = [row for row in rows if row['kind'] == 'pb']
    chains = [row for row in rows if row['kind'] == 'pb-chain']
    assert len(firmware_rows) <= 1 and len(pbs) <= 64 and len(chains) <= 8
    assert 10 <= len(mails) <= 512 and 1 <= len(lists) <= 256 and len(dma) <= 8
    assert [row['index'] for row in mails[:10]] == list(range(1, 11))
    bootstrap = [row['value'] for row in mails[:10]]
    assert bootstrap[::2] == [0x80f3a001, 0x80f3c002, 0x80f3a002, 0x80f3b002, 0x80f3d001]
    address, size = bootstrap[1], bootstrap[5]
    assert 0 < size <= 8192
    public = Path(__file__).resolve().parent
    dol_path = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
    assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
    dol = dol_path.read_bytes()
    layout = struct.unpack('>64I', dol[:256])
    section = next(i for i in range(18) if layout[18 + i] <= address
        and address + size <= layout[18 + i] + layout[36 + i])
    offset = layout[section] + address - layout[18 + section]
    firmware = dol[offset:offset + size]
    value = 0
    for byte in firmware:
        value ^= byte
        value = ((value << 3) | (value >> 29)) & 0xffffffff
    assert value == 0x4cc52064
    cache = Path(tempfile.mkdtemp(prefix='openshsm-dsp-live-evidence-', dir='/private/tmp'))
    (cache / 'events.snapshot.jsonl').write_bytes(complete)
    snapshots = []
    for kind, selected, template, maximum in [
            ('list', lists, 'dsp-list-{:03d}.bin', 512), ('dma', dma, 'dsp-dma-{:02d}.bin', 8192)]:
        for row in selected:
            assert 0 <= row['capturedBytes'] <= maximum
            if not row['saved']:
                assert row['capturedBytes'] == 0
                continue
            name = template.format(row['index'])
            source = directory / name
            data = source.read_bytes()
            assert len(data) == row['capturedBytes']
            if kind == 'list':
                assert row['wordSizeAssumption'] == 2 and len(data) == row['declaredUnits'] * 2
            (cache / name).write_bytes(data)
            snapshots.append({'kind': kind, 'index': row['index'], 'path': str(cache / name),
                'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                'wordsPrefix': [f'{word:04X}' for word in struct.unpack(f'>{len(data) // 2}H', data)[:32]]})
    live_firmware = None
    if firmware_rows and firmware_rows[0]['saved']:
        row = firmware_rows[0]
        assert row['capturedBytes'] == row['requestedBytes'] == 8192
        data = (directory / 'dsp-firmware-01.bin').read_bytes()
        assert len(data) == 8192
        live_hash = 0
        for byte in data:
            live_hash ^= byte
            live_hash = ((live_hash << 3) | (live_hash >> 29)) & 0xffffffff
        assert live_hash == row['ectorHash']
        target = cache / 'dsp-firmware-01.bin'
        target.write_bytes(data)
        live_firmware = {'path': str(target), 'sha256': sha(target), 'ectorHash': f'{live_hash:08X}',
            'exactOwnedDOLCandidateMatch': data == firmware}
    for row in pbs:
        assert 1 <= row['job'] <= 4 and 1 <= row['node'] <= 16
        assert row['profile'] == 0x4cc52064 and live_firmware and live_firmware['ectorHash'] == '4CC52064'
        if not row['saved']:
            assert row['capturedBytes'] == 0
            continue
        assert row['capturedBytes'] == 300
        name = f'dsp-pb-{row["job"]:02d}-{row["node"]:02d}.bin'
        data = (directory / name).read_bytes()
        assert len(data) == 300
        assert struct.unpack('>I', data[:4])[0] == row['nextAddress']
        assert struct.unpack('>H', data[16:18])[0] == row['running']
        target = cache / name
        target.write_bytes(data)
        snapshots.append({'kind': 'pb', 'job': row['job'], 'node': row['node'], 'path': str(target),
            'address': row['address'], 'sha256': sha(target), 'bytes': len(data)})
    report = {'result': 'LIVE_SHSM_DSP_LISTS_CAPTURED_STATIC_UCODE_AXWII_CANDIDATE_IDENTIFIED',
        'pid': record['pid'], 'liveAtRecordCreation': record['result'] == 'USER_PLAY_RUNNING_WITHOUT_DEADLINE',
        'playPath': str(play_path), 'buildSha256': sha(build_path),
        'mailRows': len(mails), 'listRows': len(lists), 'dmaRows': len(dma),
        'bootstrapMessages': [f'{word:08X}' for word in bootstrap],
        'liveRAMFirmwareCandidate': live_firmware, 'pbNodes': len(pbs), 'pbChains': chains,
        'staticDOLFirmwareCandidate': {'address': f'{address:08X}', 'size': size,
            'sha256': hashlib.sha256(firmware).hexdigest(), 'ectorHash': f'{value:08X}',
            'factoryReferenceMatch': 'AXWiiUCode'}, 'snapshots': snapshots,
        'dependencies': {str(path): sha(path) for path in [Path(__file__), record_path, build_path, dol_path]},
        'references': ['https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Common/Hash.cpp',
            'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/HW/DSPHLE/UCodes/UCodes.cpp'],
        'limits': ['Actual live mailbox/list/DMA snapshots, no diagnostic guest input or service substitution.',
            'Static firmware from owned DOL; optional live RAM snapshot separately compared when present. Neither proves actual DSP instruction execution.',
            'Ector hash matches primary factory reference, not a hardware or fullaudio/mixer acceptance.',
            'Snapshot freezes current complete records; does not stop or limit the still-running game.',
            '16-bit command schema independently checked; optional PB snapshots are pre-execution only, not voice PCM/reply-order verification.',
            'All snapshots private; no original binary data is published.']}
    path = cache / 'evidence.json'
    for dependency in (font_path, ax_path):
        if dependency:
            report['dependencies'][str(dependency)] = sha(dependency)
    report['axBuildPath'] = str(ax_path) if ax_path else None
    report['executableSha256'] = record['executableSha256']
    if record['result'] == 'USER_PLAY_EXITED':
        logs = [play_path / name for name in ('runtime-prefix.log', 'runtime-tail.log')]
        report['closedRunAudioCallbacks'] = summarize_audio_callbacks([log.read_text() for log in logs])
        for log in logs:
            report['dependencies'][str(log)] = sha(log)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, 'lists=', len(lists), 'candidate Ector=', f'{value:08X}', flush=True)


if __name__ == '__main__':
    main()
