"""Validate original SI packets, completion and final type callback on None ports."""
from pathlib import Path
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
original_header = struct.unpack('>64I', original[:256])

def offset(address, header):
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    return header[section] + address - header[18 + section]

def branch_target(image, address, header):
    word = struct.unpack_from('>I', image, offset(address, header))[0]
    assert word >> 26 == 18 and word & 3 == 0
    displacement = word & 0x03fffffc
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return address + displacement

reports = []
for suffix in ('', '-callback'):
    output = private / ('dolphin-si-query' + suffix)
    generation_path, capture_path = output / 'generation.json', output / 'fpr-init-true-dolphin.json'
    generation = json.loads(generation_path.read_text())
    capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
    builder = 'build_si_query_callback_dolphin.py' if suffix else 'build_si_query_dolphin.py'
    runner = 'run_si_query_callback_dolphin.ps1' if suffix else 'run_si_query_dolphin.ps1'
    assert generation['originalSha256'] == sha(original_path)
    assert generation['generatorSha256'] == sha(experiment / builder)
    assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
    assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
    if suffix:
        assert generation['baseGeneratorSha256'] == sha(experiment / 'build_si_query_dolphin.py')
    assert capture['records'] == len(generation['records']) == 16 and capture['accurateCache'] == 'True'
    assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'fpr-init.dol')
    assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / runner)
    assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
    assert 'Dolphin.Core.CPUCore=0' in capture['arguments'] and '-v Null' in capture['arguments']
    for channel in range(4):
        assert f'Dolphin.Core.SIDevice{channel}=0' in capture['arguments']
    image = (output / 'fpr-init.dol').read_bytes()
    header = struct.unpack('>64I', image[:256])
    allowed = set()
    assert len(generation['patches']) == 2
    for patch in generation['patches']:
        assert patch['address'] in (0x8020fe30, 0x8020fe8c)
        assert patch['offset'] == offset(patch['address'], original_header)
        assert struct.unpack_from('>I', original, patch['offset'])[0] == patch['opcode']
        allowed.update(range(patch['offset'], patch['offset'] + 4))
        assert branch_target(image, patch['address'], original_header) == patch['trampoline']
        words = struct.unpack_from('>10I', image, offset(patch['trampoline'], header))
        assert words[:2] == (0x9161fff8, 0x9181fffc)
        assert words[4] == 0x816b0000 and words[5] == 0x900b0000 | patch['slot']
        assert words[6:9] == (0x8161fff8, 0x8181fffc, patch['opcode'])
        assert branch_target(image, patch['trampoline'] + 36, header) == patch['address'] + 4
    assert {i for i in range(256, len(original)) if original[i] != image[i]} <= allowed
    data = base64.b64decode(capture['data'])
    assert len(data) == 16 * 736
    values, accumulated_status = [], 0
    for case in generation['records']:
        index, channel = case['index'], case['channel']
        row = data[index * 736:(index + 1) * 736]
        assert row[:16] == b'OSHSM_PPC_DLP001'
        assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
        actual = list(struct.unpack_from('>17I', row, 24))
        accumulated_status |= 8 << ((3 - channel) * 8)
        completed_control = 0xa0010300 | channel << 1
        written_control = (0x80010301 if index == 0 else 0xa0010301) | channel << 1
        expected = [1, completed_control, accumulated_status, 0, completed_control, accumulated_status,
            8, 0x80, 0xa5, 0x20010300 | channel << 1, accumulated_status, channel, 0xffffffff, 0x10000, 0x10000, written_control, 0]
        assert actual == expected, (suffix, index, actual, expected)
        final_type = struct.unpack_from('>I', row, 92)[0] if suffix else None
        assert not suffix or final_type == 8
        values.append({**case, 'observations': actual, 'typeAfterCallback': final_type})
    reports.append({'suffix': suffix, 'values': values, 'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path), 'limits': generation['limits']})
assert [r['observations'] for r in reports[0]['values']] == [r['observations'] for r in reports[1]['values']]
(private / 'dolphin-si-query-callback/comparison.json').write_text(json.dumps({'result': 'ORIGINAL_SI_QUERY16_PACKETS_COMPLETION_CALLBACK_VALIDATED',
    'reports': reports, 'verifierSha256': sha(Path(__file__)),
    'limits': ['Two observed fixtures, not unpatched controls; completion timing/busy duration/all GPRs not proven.',
        'Disconnected SI device packet profile only; callback manually invoked, automatic IRQ/alarm and SIGetType entry scheduling remain unverified.']}, indent=2) + '\n')
print('PASS16 original SI packets + completion + final callback type8;16bus-only controls match;4None ports, no automatic IRQ claim')
