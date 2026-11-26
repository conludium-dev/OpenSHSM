"""Verify original DI OPEN after original IPC initialization, retaining SC and pending STM."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
standalone = root / 'dolphin-di-initialized'
output = root / 'dolphin-di-initialized-disc'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((standalone / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
parent = (root / 'dolphin-di-open/fpr-init.dol').read_bytes()
image = (standalone / 'fpr-init.dol').read_bytes()
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha256(original).hexdigest() == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
assert image[256:len(original)] == original[256:]
assert generation['generatorSha256'] == sha(experiment / 'build_di_initialized_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['parentHarnessSha256'] == hashlib.sha256(parent).hexdigest()
assert generation['parentGenerationSha256'] == sha(root / 'dolphin-di-open/generation.json')
assert generation['nativeInputsSha256'] == sha(root / 'mass-di-inputs-observer/observation.json')
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'DATA/sys/main.dol') == sha(standalone / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == sha(experiment / 'run_di_initialized_disc_dolphin.ps1')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['accurateCache'] == 'True' and capture['records'] == len(generation['records']) == 16
assert all(flag in capture['arguments'] for flag in ('Dolphin.Core.CPUCore=0', '-v Null', 'dolphin-di-initialized-disc-user'))
replacement = generation['initializerReplacement']
assert replacement['target'] == 0x802420b0 and replacement['originalTarget'] == 0x80243570
offset = replacement['offset']
assert image[256:offset] == parent[256:offset] and image[offset + 4:len(parent)] == parent[offset + 4:]
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
dform, pointer, branch, spr = (namespace[name] for name in ('dform', 'pointer', 'branch', 'spr'))
text = replacement['text']
expected = [dform(37, 1, 1, -16), spr(0, 8), dform(36, 0, 1, 20)]
for address, value in [(0x80528a38, 0x935e0000), (0x8052ab10, 0x93600000)]:
    pointer(expected, 11, address)
    pointer(expected, 0, value)
    expected.append(dform(36, 0, 11, 0))
assert replacement['call'] == text + len(expected) * 4
expected.append(branch(replacement['call'], 0x802420b0, True))
expected.extend([dform(32, 0, 1, 20), spr(0, 8, True), dform(14, 1, 1, 16), 0x4e800020])
assert image[len(parent):] == struct.pack('>' + 'I' * len(expected), *expected)
assert struct.unpack_from('>I', image, offset)[0] == branch(replacement['site'], text, True)
layout = list(struct.unpack('>64I', parent[:256]))
slot = replacement['slot']
assert not layout[36 + slot]
layout[slot], layout[18 + slot], layout[36 + slot] = len(parent), text, len(expected) * 4
assert image[:256] == struct.pack('>64I', *layout)
data = base64.b64decode(capture['data'])
assert len(data) == 16 * 736
control = json.loads((root / 'dolphin-sysconf-long-disc/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
control_data = base64.b64decode(control['data'])
assert data[736:2208] == control_data[736:2208]
profile = Path('_scratch/tmp/dolphin-di-initialized-disc-user')
conf = (profile / 'Wii/shared2/sys/SYSCONF').read_bytes()
product = (profile / 'Wii/title/00000001/00000002/data/setting.txt').read_bytes()
assert len(conf) == 16384 and len(product) == 256
assert base64.b64decode(capture['confPhysical']) == conf == base64.b64decode(control['confPhysical'])
assert base64.b64decode(capture['productPhysical']) == product
pending = control_data[2 * 736:3 * 736]


def check(row, index):
    assert row[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    assert struct.unpack_from('>2I', row, 400) == (1 if index in (6, 7) else 0, 0xa032)
    assert struct.unpack_from('>3I', row, 608) == (0, 1, 1)
    assert struct.unpack_from('>3I', row, 720) == (0, 0x4000, 0x100)
    assert row[448:480] == row[480:512] == conf[:32]
    assert row[192:256] == pending[192:256] and row[256:320] == pending[256:320]
    assert row[416:448] == bytes(32)
    state = list(struct.unpack_from('>22I', row, 24))
    assert state[:3] == [0x38, 0x135e00e0 if index == 5 else 0x135e0080, 0x10100]
    assert state[3:15] == [1, 0, 0, 0, 0x80492658, 0x80492658, 0x492658, 0x80492658, 0x20001, 0, 0x935e0060, 0x50]
    count = 15 if index == 5 else 16 if index == 6 else 17
    assert state[15:19] == [count, count, count & 15, count & 15]
    if index >= 6:
        assert state[19] == 0x8021a890
    assert state[20:] == ([0xa032, 0xa032] if index == 5 else [0x2032, 0xa032])
    return {'index': index, 'apiReturn': 1 if index in (6, 7) else 0, 'states': state}


cases = [check(data[index * 736:(index + 1) * 736], index) for index in range(5, 16)]
locations = [16, 20, 24, 28, 32, 36, 52, 76, 80, 84, 88, 92, 96, 100, 104, 108,
    192, 256, 288, 400, 404, 416, 448, 480, 608, 612, 616, 720, 724, 728]
for location in locations:
    mutant = bytearray(data[6 * 736:7 * 736])
    mutant[location] ^= 1
    try:
        check(mutant, 6)
    except AssertionError:
        pass
    else:
        raise AssertionError('False DI success, lost pending STM or changed SC/heap accepted')
log = profile / 'Logs/dolphin.log'
log_text = log.read_text(errors='replace')
for descriptor in (3, 4):
    assert log_text.count('Opening /dev/di (mode 0, fd ' + str(descriptor) + ')') == 1
proof = root / 'di-init-source/ghidra/verification.json'
ghidra = json.loads(proof.read_text())
assert ghidra['runnerSha256'] == sha(experiment / 'verify_di_init_ghidra.py')
for row in ghidra['records']:
    assert sha(proof.parent / (row['name'] + '.asm')) == row['assemblySha256']
    assert sha(proof.parent / (row['name'] + '.c')) == row['decompiledSha256']
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_IPC_INIT_SC_DI_TWO_OPENS_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(standalone / 'generation.json'),
    'captureSha256': sha(capture_path), 'logSha256': sha(log), 'ghidraSha256': sha(proof),
    'cases': cases, 'mutantsRejected': len(locations), 'observedDiDescriptors': [3, 4],
    'limits': generation['limits'] + ['Dolphin original SDK CPU oracle, not physical retail/cycles; no DI ioctl or disc-read evidence yet.',
        'Descriptor observations come from IOS logs and original API returns, not a direct DI-global capture.']}, indent=2) + '\n')
print('PASS original IPCCltInit/SC/whole DVDLowInit twice/API1/DI FDs3-4/heap/queues/pendingSTM;30mutants; no disc-read claim')
