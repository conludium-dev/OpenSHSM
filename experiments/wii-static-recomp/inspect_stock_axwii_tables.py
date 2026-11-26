"""Resolve captured compressor pointers against the user's private Wii DOL, without launching it."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import tempfile
from verify_stock_axwii_schema import sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text())
    assert evidence['result'] == 'LIVE_SHSM_DSP_LISTS_CAPTURED_STATIC_UCODE_AXWII_CANDIDATE_IDENTIFIED'
    assert evidence['staticDOLFirmwareCandidate']['ectorHash'] == '4CC52064'
    public = Path(__file__).resolve().parent
    dol_path = public.parents[1] / 'work/private-game/disc/DATA/sys/main.dol'
    assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
    dol = dol_path.read_bytes()
    layout = struct.unpack('>64I', dol[:256])
    widths = [2, 2, 2, 2, 2, 5, 5, 5, 13, 13, 4, 5, 5, 8, 0]
    commands = []
    for row in evidence['snapshots']:
        if row['kind'] != 'list':
            continue
        assert sha(row['path']) == row['sha256']
        data = Path(row['path']).read_bytes()
        assert len(data) == row['bytes'] and 0 < len(data) <= 512 and len(data) % 2 == 0
        words = struct.unpack(f'>{len(data) // 2}H', data)
        cursor = 0
        ended = False
        while cursor < len(words):
            opcode = words[cursor]
            cursor += 1
            assert opcode < len(widths)
            count = widths[opcode]
            assert cursor + count <= len(words)
            arguments = words[cursor:cursor + count]
            cursor += count
            if opcode == 10:
                commands.append({'listIndex': row['index'], 'threshold': arguments[0],
                    'releaseFrames': arguments[1], 'tableAddress': arguments[2] << 16 | arguments[3]})
            if opcode == 14:
                ended = True
                break
        assert ended
    assert commands
    profiles = sorted({(row['threshold'], row['releaseFrames'], row['tableAddress']) for row in commands})
    cache = Path(tempfile.mkdtemp(prefix='openshsm-axwii-tables-', dir='/private/tmp'))
    tables = []
    for threshold, release, address in profiles:
        assert release <= 10
        entry_count = 11 + release
        size = entry_count * 192
        section = next(i for i in range(18) if layout[18 + i] <= address and
            address + size <= layout[18 + i] + layout[36 + i])
        offset = layout[section] + address - layout[18 + section]
        data = dol[offset:offset + size]
        assert len(data) == size
        coefficients = struct.unpack(f'>{size // 2}H', data)
        target = cache / f'compressor-{address:08x}-{release}.bin'
        target.write_bytes(data)
        entries = [coefficients[index * 96:(index + 1) * 96] for index in range(entry_count)]
        tables.append({'address': address, 'threshold': threshold, 'releaseFrames': release,
            'path': str(target), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': size,
            'dolSection': section, 'dolFileOffset': offset, 'entries': entry_count,
            'minimumCoefficient': min(coefficients), 'maximumCoefficient': max(coefficients),
            'entryRanges': [{'minimum': min(entry), 'maximum': max(entry)} for entry in entries],
            'beforeFirmwareBytes': int(evidence['staticDOLFirmwareCandidate']['address'], 16) - (address + size)})
    report = {'result': 'CAPTURED_AXWII_COMPRESSOR_POINTERS_MAPPED_TO_OWN_DOL',
        'capturedCompressorCommands': len(commands), 'commands': commands, 'tables': tables,
        'dependencies': {str(path.resolve()): sha(path) for path in (Path(__file__), args.evidence, dol_path)},
        'limits': ['Actual captured command arguments; numerical table layout inferred from independently pinned AX compressor reference.',
            'Bytes mapped to the owned Wii US revision0 DOL, not a live RAM snapshot: runtime modification remains unverified.',
            'Only compressor coefficient provenance; not real PB/sample/DROM/mixer/IRQ/audio or physical Wii acceptance.',
            'Original bytes remain private outside public source; no game/window/process mutation.']}
    output = cache / 'tables.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], output, 'commands', len(commands), 'tables', len(tables), flush=True)


if __name__ == '__main__':
    main()
