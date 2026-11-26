"""Verify the original command/DMA/cache trace against an unpatched control."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'dolphin-sram'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
reports = []
for name in ('dolphin-sram', 'dolphin-sram-unobserved'):
    directory = private / name
    generation_path = directory / 'generation.json'
    capture_path = directory / 'fpr-init-true-dolphin.json'
    generation = json.loads(generation_path.read_text())
    capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
    assert generation['originalSha256'] == sha(original_path)
    assert generation['generatorSha256'] == sha(experiment / 'build_sram_dolphin.py')
    assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
    assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
    assert generation['wrapperSha256'] == capture['scriptSha256'].lower() == sha(experiment / 'run_sram_dolphin.ps1')
    assert generation['harnessSha256'] == capture['harnessSha256'].lower() == sha(directory / 'fpr-init.dol')
    assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
    assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
    for required in ('Dolphin.Core.CPUCore=0', 'Dolphin.Core.SerialPort1=255', 'dolphin-sram-user', '-v Null'):
        assert required in capture['arguments']
    image = (directory / 'fpr-init.dol').read_bytes()
    header = struct.unpack('>64I', image[:256])
    def offset(address):
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        return header[section] + address - header[18 + section]
    observed = name == 'dolphin-sram'
    assert generation['observed'] == observed
    assert len(generation['patches']) == (6 if observed else 0)
    allowed = set()
    for patch in generation['patches']:
        assert patch['offset'] == offset(patch['address'])
        assert struct.unpack_from('>I', original, patch['offset'])[0] == patch['opcode']
        word = struct.unpack_from('>I', image, patch['offset'])[0]
        assert word >> 26 == 18 and word & 3 == 0
        displacement = word & 0x03fffffc
        if displacement & 0x02000000:
            displacement -= 0x04000000
        assert patch['address'] + displacement == patch['trampoline']
        words = patch['words']
        assert list(struct.unpack_from('>' + 'I' * len(words), image, offset(patch['trampoline']))) == words
        assert words[:3] == [patch['opcode'], 0x9161fff8, 0x9181fffc]
        assert words[-3:-1] == [0x8161fff8, 0x8181fffc]
        displacement = words[-1] & 0x03fffffc
        if displacement & 0x02000000:
            displacement -= 0x04000000
        assert words[-1] >> 26 == 18 and words[-1] & 3 == 0
        assert patch['trampoline'] + (len(words) - 1) * 4 + displacement == patch['address'] + 4
        allowed.update(range(patch['offset'], patch['offset'] + 4))
    assert {i for i in range(256, len(original)) if original[i] != image[i]} <= allowed
    data = base64.b64decode(capture['data'])
    assert len(data) == 16 * 736
    values = []
    for case in generation['records']:
        index = case['index']
        row = data[index * 736:(index + 1) * 736]
        assert row[:16] == b'OSHSM_PPC_DLP001'
        assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
        before_csr = 0x3800 if index == 0 else 0x3808
        after_csr = 0x1c0c if index == 0 else 0x1808
        before_control, before_data = (0, 0) if index == 0 else (2, 0x20000100)
        after_pi = 0x10010 if index == 0 else 0x10000
        scalar = list(struct.unpack_from('>10I', row, 24))
        assert scalar == [1, 0x2030, before_csr, before_control, before_data, 0x10000, after_csr, 2, 0x20000100, after_pi]
        scb = row[64:144]
        assert struct.unpack_from('>4I', scb, 64) == (64, 0, 0, 1)
        ecb = list(struct.unpack_from('>16I', row, 144))
        assert ecb == [0, 0, 0, 0, 0, 0x8053ffe8, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        abi = list(struct.unpack_from('>4I', row, 388))
        assert abi == [0x80540000, 0x805335e0, 0x8052e720, 0xc0680000 + index * 736]
        assert struct.unpack_from('>Q', row, 704)[0] & 0xffffffff == case['ni'] * 4
        settings = scb[:64]
        checksum, inverse = struct.unpack_from('>2H', settings)
        source_words = struct.unpack_from('>4H', settings, 12)
        assert checksum == sum(source_words) & 0xffff
        assert inverse == sum(word ^ 0xffff for word in source_words) & 0xffff
        phase = None
        if observed:
            phase = list(struct.unpack_from('>13I', row, 208))
            csr = 0x1d3c if index == 0 else 0x1938
            assert phase == [0x20000100, 0x35, 0x34, csr, 0x80492600, 0x80492600, 64, 64, 3, 2, csr, after_pi, 1]
            assert row[260:324] == row[324:388] == settings
        else:
            assert row[208:388] == bytes(180)
        values.append({**case, 'scalar': scalar, 'scbHex': scb.hex(), 'ecb': ecb, 'abi': abi, 'phase': phase})
    reports.append({'values': values, 'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path)})
for observed, control in zip(reports[0]['values'], reports[1]['values']):
    for field in ('scalar', 'scbHex', 'ecb', 'abi'):
        assert observed[field] == control[field]
settings = {row['scbHex'][:128] for row in reports[0]['values']}
assert len(settings) == 1
ghidra_path = output / 'ghidra/verification.json'
ghidra = json.loads(ghidra_path.read_text())
assert ghidra['runnerSha256'] == sha(experiment / 'verify_sram_ghidra.py')
assert ghidra['scriptSha256'] == sha(experiment / 'ExportFormatSpan.java')
original_functions = []
original_header = struct.unpack('>64I', original[:256])
for row, entry in zip(ghidra['records'], (0x80219670, 0x8020dba0, 0x80219870)):
    assert row['discoveredBodyBytes'] == row['bytes']
    assert row['objectSha256'] == sha(private / 'dtk-output/obj/auto_03_802045CC_text.o')
    assert row['assemblySha256'] == sha(ghidra_path.parent / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(ghidra_path.parent / (row['name'] + '.c'))
    section = next(i for i in range(7) if original_header[18 + i] <= entry < original_header[18 + i] + original_header[36 + i])
    location = original_header[section] + entry - original_header[18 + section]
    original_functions.append({'name': row['name'], 'address': entry, 'bytes': row['bytes'],
        'dolSpanSha256': hashlib.sha256(original[location:location + row['bytes']]).hexdigest()})
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_SRAM16_COMMAND_DMA_CACHE_UNPATCHED16_VALIDATED',
    'reports': reports, 'verifierSha256': sha(Path(__file__)), 'settingsSha256': hashlib.sha256(bytes.fromhex(next(iter(settings)))).hexdigest(),
    'ghidraSha256': sha(ghidra_path), 'originalFunctions': original_functions,
    'originalBehavior': ['Original command20000100, immediate control35→34, DMA address80492600/length64/control3→2, SCB/ECB/cache readback and restored fixture ABI.',
        'Six replaying observers match the unpatched control final scalar/SCB/ECB/ABI observations in16calls each.'],
    'pcAdaptation': ['64settings bytes come from the isolated Dolphin laboratory SRAM defaults, not an original game asset or personal Wii settings.',
        'Prepared ECB/SCB/MSR/HID/NI/r2-r13, observer timing and laboratory profile; r3 is merely observed from a void function.'],
    'limits': ['No native DMA implementation, retail boot advance, all-register/timing/physical Wii or first-image/menu proof from this capture.']}, indent=2) + '\n')
print('PASS16 whole original SRAM command/DMA/cache/ABI +16unpatched controls; emulator settings identified as adapter data')
