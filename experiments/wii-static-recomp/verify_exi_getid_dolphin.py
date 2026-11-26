"""Validate whole GetID capture, replayed observer words and provenance."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-exi-getid')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path, capture_path = output / 'generation.json', output / 'fpr-init-true-dolphin.json'
generation = json.loads(generation_path.read_text())
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
assert ' -C Dolphin.Core.SerialPort1=255 ' in capture['arguments']
assert ' -C Dolphin.Core.CPUCore=0 ' in capture['arguments']
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_exi_getid_dolphin.ps1')
for key, name in [('generatorSha256', 'build_exi_getid_dolphin.py'), ('helperSha256', 'build_dolphin_probe.py'), ('baseRunnerSha256', 'run_dolphin_probe.ps1')]:
    assert generation[key] == sha(experiment / name)
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original, image = original_path.read_bytes(), (output / 'fpr-init.dol').read_bytes()
header = struct.unpack('>64I', image[:256])
def offset_for(address):
    section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    return header[section] + address - header[18 + section]
allowed = set()
expected = {0x8020da84: 0x90036810, 0x8020dac4: 0x9083680c, 0x8020dd30: 0x80036810}
assert {p['address']: p['opcode'] for p in generation['patches']} == expected
for patch in generation['patches']:
    offset = patch['offset']
    assert offset == offset_for(patch['address'])
    assert struct.unpack_from('>I', original, offset)[0] == patch['opcode']
    patched = struct.unpack_from('>I', image, offset)[0]
    assert patched >> 26 == 18 and patched & 3 == 0
    displacement = patched & 0x03fffffc
    if displacement & 0x02000000:
        displacement -= 0x04000000
    assert patch['address'] + displacement == patch['trampoline']
    assert struct.unpack_from('>I', image, offset_for(patch['trampoline']))[0] == patch['opcode']
    allowed.update(range(offset, offset + 4))
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= allowed
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
observations = []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    read = lambda offset: struct.unpack_from('>I', row, offset)[0]
    assert row[:16] == b'OSHSM_PPC_DLP001' and (read(16), read(20)) == (0xc001cafe, index)
    assert read(44) == 0x2030
    assert struct.unpack_from('>Q', row, 704)[0] & 0xffffffff == record['ni'] * 4
    assert read(152) == 2
    phases = []
    for phase in range(2):
        value, control, csr, immediate = struct.unpack_from('>4I', row, 160 + phase * 32)
        assert value == (0x15 if phase == 0 else 0x31)
        assert control == value & ~1
        phases.append({'writtenControl': value, 'controlAfter': control, 'csrAfter': csr, 'dataAfter': immediate})
    assert read(144) == 0 and read(148) == read(28) == read(72) == 0
    assert read(24) == 1 and read(68) == 0x30 and read(76) == 0
    observations.append({**record, 'returnValue': read(24), 'destinationAfter': read(28),
                         'csrBefore': read(32), 'controlBefore': read(36), 'dataBefore': read(40),
                         'causeBefore': read(56), 'causeAfter': read(60),
                         'csrAfter': read(64), 'controlAfter': read(68), 'dataAfter': read(72),
                         'cachedIdAfter': read(76), 'ecbAfter': list(struct.unpack_from('>16I', row, 80)),
                         'commandWritten': read(144), 'responseRead': read(148), 'phases': phases})
baseline_dir = output.with_name('dolphin-exi-getid-unobserved')
baseline_generation_path = baseline_dir / 'generation.json'
baseline_capture_path = baseline_dir / 'fpr-init-true-dolphin.json'
baseline_generation = json.loads(baseline_generation_path.read_text())
baseline_capture = json.loads(baseline_capture_path.read_text(encoding='utf-8-sig'))
assert baseline_generation['patches'] == []
assert baseline_generation['records'] == generation['records']
assert baseline_generation['originalSha256'] == generation['originalSha256']
assert baseline_generation['generatorSha256'] == sha(experiment / 'build_exi_getid_unobserved_dolphin.py')
assert baseline_generation['baseGeneratorSha256'] == generation['generatorSha256']
assert baseline_generation['helperSha256'] == generation['helperSha256']
assert baseline_generation['baseRunnerSha256'] == generation['baseRunnerSha256']
assert baseline_capture['records'] == 16 and baseline_capture['accurateCache'] == 'True'
assert ' -C Dolphin.Core.SerialPort1=255 ' in baseline_capture['arguments']
assert baseline_capture['emulatorSha256'] == capture['emulatorSha256']
assert baseline_capture['scriptSha256'].lower() == baseline_generation['wrapperSha256'] == sha(experiment / 'run_exi_getid_unobserved_dolphin.ps1')
assert baseline_capture['harnessSha256'].lower() == baseline_generation['harnessSha256'] == sha(baseline_dir / 'fpr-init.dol')
baseline_image = (baseline_dir / 'fpr-init.dol').read_bytes()
assert baseline_image[256:len(original)] == original[256:]
baseline_data = base64.b64decode(baseline_capture['data'])
assert len(baseline_data) == len(data)
for index in range(16):
    row = baseline_data[index * 736:(index + 1) * 736]
    observed_row = data[index * 736:(index + 1) * 736]
    assert row[:144] == observed_row[:144]
    assert row[704:712] == observed_row[704:712]
    assert row[144:224] == bytes(80)
report = {'result': 'ORIGINAL_EXI_GETID16_COMPLETE_CALLS_AND_UNPATCHED16_VALIDATED', 'cases': 16,
          'serialPort1': {'value': 255, 'type': 'None', 'evidence': 'Dolphin EXI_Device.h EXIDeviceType::None=0xFF; capture arguments'},
          'observations': observations, 'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path),
          'verifierSha256': sha(Path(__file__)), 'limits': generation['limits'],
          'unpatchedCases': 16, 'unpatchedFinalSnapshotsEqual': True,
          'unpatchedGenerationSha256': sha(baseline_generation_path), 'unpatchedCaptureSha256': sha(baseline_capture_path)}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS16 original whole GetID calls: command0/control15→14, read31→30/ID0/return1; NI0/1')
print('CSR/PI first:', observations[0]['csrBefore'], observations[0]['csrAfter'], observations[0]['causeBefore'], observations[0]['causeAfter'])
print('CSR/PI repeated:', observations[1]['csrBefore'], observations[1]['csrAfter'], observations[1]['causeBefore'], observations[1]['causeAfter'])
print('PASS16 unpatched original calls match final return/ID/CSR/control/data/PI/cache/ECB/MSR/FPSCR snapshots')
