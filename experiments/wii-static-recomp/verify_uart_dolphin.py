"""Validate whole EUART captures and the unpatched observer control run."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-uart')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
datasets = []
for unobserved in (False, True):
    folder = output.with_name('dolphin-uart-unobserved') if unobserved else output
    suffix = '_unobserved' if unobserved else ''
    generation_path, capture_path = folder / 'generation.json', folder / 'fpr-init-true-dolphin.json'
    generation = json.loads(generation_path.read_text())
    capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
    assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
    assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(folder / 'fpr-init.dol')
    assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / ('run_uart' + suffix + '_dolphin.ps1'))
    assert generation['generatorSha256'] == sha(experiment / ('build_uart' + suffix + '_dolphin.py'))
    assert generation['baseGeneratorSha256'] == sha(experiment / 'build_exi_getid_dolphin.py')
    if unobserved:
        assert generation['baseUartGeneratorSha256'] == sha(experiment / 'build_uart_dolphin.py')
    assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
    assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
    assert generation['originalSha256'] == sha(original_path)
    assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
    assert ' -C Dolphin.Core.SerialPort1=255 ' in capture['arguments']
    image = (folder / 'fpr-init.dol').read_bytes()
    allowed = set()
    if unobserved:
        assert generation['patches'] == []
    else:
        assert {p['address']: p['opcode'] for p in generation['patches']} == {0x8020da84: 0x90036810, 0x8020dac4: 0x9083680c, 0x8020dd30: 0x80036810}
        header = struct.unpack('>64I', image[:256])
        for patch in generation['patches']:
            assert struct.unpack_from('>I', original, patch['offset'])[0] == patch['opcode']
            branch = struct.unpack_from('>I', image, patch['offset'])[0]
            displacement = branch & 0x03fffffc
            if displacement & 0x02000000:
                displacement -= 0x04000000
            assert branch >> 26 == 18 and branch & 3 == 0 and patch['address'] + displacement == patch['trampoline']
            section = next(i for i in range(7) if header[18 + i] <= patch['trampoline'] < header[18 + i] + header[36 + i])
            offset = header[section] + patch['trampoline'] - header[18 + section]
            assert struct.unpack_from('>I', image, offset)[0] == patch['opcode']
            allowed.update(range(patch['offset'], patch['offset'] + 4))
    assert {i for i in range(256, len(original)) if original[i] != image[i]} <= allowed
    data = base64.b64decode(capture['data'])
    assert len(data) == 16 * 736
    datasets.append((generation, capture, data, generation_path, capture_path))
generation, capture, data, generation_path, capture_path = datasets[0]
assert datasets[1][0]['records'] == generation['records']
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    baseline = datasets[1][2][index * 736:(index + 1) * 736]
    read = lambda offset: struct.unpack_from('>I', row, offset)[0]
    assert row[:16] == b'OSHSM_PPC_DLP001' and (read(16), read(20)) == (0xc001cafe, index)
    assert baseline[:144] == row[:144] and baseline[640:656] == row[640:656] and baseline[704:712] == row[704:712]
    assert baseline[144:640] == bytes(496)
    assert read(24) == 0 and read(76) == 1 and read(44) == 0x2030
    assert struct.unpack_from('>Q', row, 704)[0] & 0xffffffff == record['ni'] * 4
    payload = bytes.fromhex(record['payloadHex']).replace(b'\n', b'\r')
    assert row[640:640 + len(payload)] == payload
    expected_data = ([0xb0000000, 0xf2000000, 0xb0000000, 0xf3000000] if record['resetUartInit'] else [])
    expected_data += [0x30000100, 0, 0xb0000100] + [byte << 24 for byte in payload]
    phases = [list(struct.unpack_from('>4I', row, 160 + phase * 32)) for phase in range(read(152))]
    assert len(phases) == len(expected_data) and [phase[3] for phase in phases] == expected_data
    for phase, values in enumerate(phases):
        expected_control = 0x31 if phase == (5 if record['resetUartInit'] else 1) else 0x35
        assert values[0] == expected_control and values[1] == expected_control & ~1
    observations.append({**record, 'returnValue': read(24), 'payloadWordAfter': read(28), 'csrBeforeFixtureClear': read(32),
        'controlBefore': read(36), 'dataBefore': read(40), 'causeBeforeFixtureClear': read(56), 'causeAfter': read(60),
        'csrAfter': read(64), 'controlAfter': read(68), 'dataAfter': read(72), 'uartInitializedAfter': read(76),
        'ecbAfter': list(struct.unpack_from('>16I', row, 80)), 'bufferAfterHex': row[640:656].hex(), 'phases': phases})
report = {'result': 'ORIGINAL_WHOLE_EUART16_AND_UNPATCHED16_PASS', 'cases': 16, 'phaseSnapshots': sum(len(row['phases']) for row in observations),
    'observations': observations, 'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path),
    'unpatchedCaptureSha256': sha(datasets[1][4]), 'unpatchedGenerationSha256': sha(datasets[1][3]), 'verifierSha256': sha(Path(__file__)),
    'limits': generation['limits'] + ['CSR/cause before snapshot precedes the disclosed optional EXTINT-clear fixture; not the state after that clear.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS16 whole UART writes/unpatched16/F2-F3 init/empty queue/CR normalization;', report['phaseSnapshots'], 'phases')
