"""Verify whole original DVD inquiry/ES execution and captured inquiry payload; no trace claim."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import struct

root = Path('work/private-game/static-recomp')
experiment = Path('experiments/wii-static-recomp')
output, standalone = root / 'dolphin-di-burst-disc', root / 'dolphin-di-burst'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((standalone / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
parent = (root / 'dolphin-di-initialized/fpr-init.dol').read_bytes()
image = (output / 'DATA/sys/main.dol').read_bytes()
assert generation['generatorSha256'] == sha(experiment / 'build_di_burst_dolphin.py')
assert generation['parentHarnessSha256'] == hashlib.sha256(parent).hexdigest()
assert generation['burstParentGeneratorSha256'] == sha(experiment / 'build_di86_dolphin.py')
assert generation['nativeBurstInputsSha256'] == sha(root / 'mass-di86-idle-observer/observation.json')
assert generation['harnessSha256'] == sha(output / 'DATA/sys/main.dol') == sha(standalone / 'fpr-init.dol') == capture['harnessSha256'].lower()
assert capture['scriptSha256'].lower() == sha(experiment / 'run_di_burst_disc_dolphin.ps1')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['records'] == 16 and capture['accurateCache'] == 'True'
assert all(flag in capture['arguments'] for flag in ('Dolphin.Core.CPUCore=0', '-v Null', 'dolphin-di-burst-disc-user'))
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
dform, pointer, branch, spr = (namespace[name] for name in ('dform', 'pointer', 'branch', 'spr'))
patch, burst = generation['di86Call'], generation['burst']
code = [dform(37, 1, 1, -16), spr(0, 8), dform(36, 0, 1, 20)]
pointer(code, 0, 0x2032)
code.append(0x7c000124)
for register, value in [(3, 0x80492280), (4, 0x80492260), (5, 0x80211060)]:
    pointer(code, register, value)
assert burst['inquiryCall'] == patch['text'] + len(code) * 4
code.append(branch(burst['inquiryCall'], 0x80223a50, True))
code.extend([dform(36, 3, 30, 408), 0x7c0000a6, dform(36, 0, 30, 412)])
assert burst['esCall'] == patch['text'] + len(code) * 4
code.append(branch(burst['esCall'], 0x80249790, True))
code.extend([dform(32, 0, 1, 20), spr(0, 8, True), dform(14, 1, 1, 16), 0x4e800020])
assert patch['resume'] == patch['text'] + len(code) * 4
code.append(dform(36, 0, 1, -4))
pointer(code, 0, 0xa032)
code.extend([0x7c000124, dform(32, 0, 1, -4), patch['replayedWord']])
code.append(branch(patch['text'] + len(code) * 4, patch['site'] + 20))
assert image[len(parent):] == struct.pack('>' + 'I' * len(code), *code)
baseline = bytearray(parent)
for offset, site, target, linked in [(burst['firstOffset'], burst['firstSite'], 0x8021f9d0, True),
    (patch['offset'], patch['site'], patch['text'], True), (patch['offset'] + 16, patch['site'] + 16, patch['resume'], False)]:
    struct.pack_into('>I', baseline, offset, branch(site, target, linked))
assert image[256:len(parent)] == baseline[256:]
layout = list(struct.unpack('>64I', parent[:256]))
slot = patch['slot']
assert not layout[36 + slot]
layout[slot], layout[18 + slot], layout[36 + slot] = len(parent), patch['text'], len(code) * 4
assert image[:256] == struct.pack('>64I', *layout)
control = json.loads((root / 'dolphin-di86-disc/fpr-init-true-dolphin.json').read_text(encoding='utf-8-sig'))
data, golden = (base64.b64decode(row['data']) for row in (capture, control))
assert len(data) == 16 * 736 and data[:6 * 736] == golden[:6 * 736]
for key in ('confPhysical', 'productPhysical'):
    assert base64.b64decode(capture[key]) == base64.b64decode(control[key])
inquiry = base64.b64decode(capture['inquiryPhysical'])
assert len(inquiry) == 32 and struct.unpack_from('>3I', inquiry) == (2, 0x20060526, 0x41000000)
assert inquiry[12:] == bytes(20)
pending = golden[2 * 736:3 * 736]


def check(row, index):
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    assert struct.unpack_from('>2I', row, 400) == (0, 0x2032 if index == 7 else 0xa032)
    if index == 7:
        assert struct.unpack_from('>2I', row, 408) == (1, 0x2032)
    assert struct.unpack_from('>3I', row, 608) == (0, 1, 1)
    assert struct.unpack_from('>3I', row, 720) == (0, 0x4000, 0x100)
    assert row[192:320] == pending[192:320] and row[416:448] == bytes(32)
    state = list(struct.unpack_from('>22I', row, 24))
    assert state[:3] == [0x38, 0x135e00e0, 0x10100]
    assert state[3:15] == [1, 0, 0, 0, 0x80492658, 0x80492658, 0x492658, 0x80492658, 0x20001, 0, 0x935e0060, 0x50]
    assert state[15:19] == [19, 19, 3, 3]
    assert state[19:] == [patch['site'] + 28, 0xa032, 0xa032]


for index in range(7, 16):
    check(data[index * 736:(index + 1) * 736], index)
locations = [16, 20, 24, 28, 32, 36, 52, 76, 80, 84, 88, 92, 96, 100, 104, 108, 192, 256, 288, 400, 404, 408, 412, 416, 608, 612, 616, 720, 724, 728]
for location in locations:
    changed = bytearray(data[7 * 736:8 * 736])
    changed[location] ^= 1
    try:
        check(changed, 7)
    except AssertionError:
        pass
    else:
        raise AssertionError('False whole inquiry/ES endpoint accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_WHOLE_DVDINIT_INQUIRY_API1_ES_API0_SETTLED_PAYLOAD32_SC_PENDING_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(standalone / 'generation.json'),
    'captureSha256': sha(capture_path), 'inquirySha256': hashlib.sha256(inquiry).hexdigest(), 'mutantsRejected': len(locations),
    'limits': generation['limits'] + ['Inquiry words are measured Dolphin laboratory drive metadata, not physical Wii identity/public asset requirement.',
        'Full concurrent packet/idle/callback order still needs replay trace; API endpoints/payload alone do not prove native equivalence.']}, indent=2) + '\n')
print('PASS whole original DVDInit/Inquiry API1-2032/ES API0-2032/full32 measured inquiry/heap0060/empty19queues/SC-STM/30mutants; burst trace next')
