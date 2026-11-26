"""Verify original DI86 API execution and settled endpoints without claiming uncaptured replies."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import struct

root = Path('work/private-game/static-recomp')
experiment = Path('experiments/wii-static-recomp')
output = root / 'dolphin-di86-disc'
standalone = root / 'dolphin-di86'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((standalone / 'generation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
control_path = root / 'dolphin-di-initialized-disc/fpr-init-true-dolphin.json'
control = json.loads(control_path.read_text(encoding='utf-8-sig'))
parent = (root / 'dolphin-di-initialized/fpr-init.dol').read_bytes()
image = (output / 'DATA/sys/main.dol').read_bytes()
assert sha(standalone / 'fpr-init.dol') == sha(output / 'DATA/sys/main.dol') == generation['harnessSha256'] == capture['harnessSha256'].lower()
assert generation['generatorSha256'] == sha(experiment / 'build_di86_dolphin.py')
assert generation['nativeInputsSha256'] == sha(root / 'mass-di86-inputs-observer/observation.json')
assert generation['parentHarnessSha256'] == hashlib.sha256(parent).hexdigest()
assert generation['parentGenerationSha256'] == sha(root / 'dolphin-di-initialized/generation.json')
assert capture['scriptSha256'].lower() == sha(experiment / 'run_di86_disc_dolphin.ps1')
assert capture['emulatorSha256'].lower() == control['emulatorSha256'].lower()
assert capture['records'] == 16 and capture['accurateCache'] == 'True'
assert all(flag in capture['arguments'] for flag in ('Dolphin.Core.CPUCore=0', '-v Null', 'dolphin-di86-disc-user'))
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
dform, pointer, branch, spr = (namespace[name] for name in ('dform', 'pointer', 'branch', 'spr'))
patch = generation['di86Call']
code = [dform(37, 1, 1, -16), spr(0, 8), dform(36, 0, 1, 20), dform(14, 3, 0, 0)]
assert patch['call'] == patch['text'] + len(code) * 4 and patch['target'] == 0x80227dd0
code.append(branch(patch['call'], patch['target'], True))
code.extend([dform(32, 0, 1, 20), spr(0, 8, True), dform(14, 1, 1, 16), 0x4e800020])
assert patch['resume'] == patch['text'] + len(code) * 4
code.append(dform(36, 0, 1, -4))
pointer(code, 0, 0xa032)
code.extend([0x7c000124, dform(32, 0, 1, -4), patch['replayedWord']])
code.append(branch(patch['text'] + len(code) * 4, patch['site'] + 20))
assert image[len(parent):] == struct.pack('>' + 'I' * len(code), *code)
baseline = bytearray(parent)
struct.pack_into('>I', baseline, patch['offset'], branch(patch['site'], patch['text'], True))
struct.pack_into('>I', baseline, patch['offset'] + 16, branch(patch['site'] + 16, patch['resume']))
assert image[256:len(parent)] == baseline[256:]
layout = list(struct.unpack('>64I', parent[:256]))
slot = patch['slot']
assert not layout[36 + slot]
layout[slot], layout[18 + slot], layout[36 + slot] = len(parent), patch['text'], len(code) * 4
assert image[:256] == struct.pack('>64I', *layout)
assert list(struct.unpack_from('>3I', image, patch['offset'] + 4)) == [dform(36, 3, 30, 400), 0x7c0000a6, dform(36, 0, 30, 404)]
data, golden = (base64.b64decode(row['data']) for row in (capture, control))
assert len(data) == 16 * 736 and data[:7 * 736] == golden[:7 * 736]
for field in ('confPhysical', 'productPhysical'):
    assert base64.b64decode(capture[field]) == base64.b64decode(control[field])
pending = golden[2 * 736:3 * 736]


def check(row, index):
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, index)
    assert struct.unpack_from('>2I', row, 400) == (1 if index == 7 else 0, 0xa032)
    assert struct.unpack_from('>3I', row, 608) == (0, 1, 1)
    assert struct.unpack_from('>3I', row, 720) == (0, 0x4000, 0x100)
    assert row[192:320] == pending[192:320] and row[416:448] == bytes(32)
    state = list(struct.unpack_from('>22I', row, 24))
    assert state[:3] == [0x38, 0x135e0080, 0x10100]
    assert state[3:15] == [1, 0, 0, 0, 0x80492658, 0x80492658, 0x492658, 0x80492658, 0x20001, 0, 0x935e0060, 0x50]
    assert state[15:19] == [17, 17, 1, 1]
    assert state[19] == patch['site'] + 28 and state[20:] == [0xa032, 0xa032]


for index in range(7, 16):
    check(data[index * 736:(index + 1) * 736], index)
locations = [16, 20, 24, 28, 32, 36, 52, 76, 80, 84, 88, 92, 96, 100, 104, 108, 192, 256, 288, 400, 404, 416, 608, 612, 616, 720, 724, 728]
for location in locations:
    changed = bytearray(data[7 * 736:8 * 736])
    changed[location] ^= 1
    try:
        check(changed, 7)
    except AssertionError:
        pass
    else:
        raise AssertionError('False API/heap/queue/SC/pending endpoint accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_DI86_API1_A032_SETTLED_HEAP_QUEUE_PENDING_SC_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(standalone / 'generation.json'),
    'captureSha256': sha(capture_path), 'controlCaptureSha256': sha(control_path), 'mutantsRejected': len(locations),
    'limits': generation['limits'] + ['API1 means accepted async request, NOT the actual IOS response value.',
        'Heap/queue settled endpoints captured; full DI reply64 and callback execution still require replay trace.']}, indent=2) + '\n')
print('PASS original DI86 API1/A032/heap0060/empty17queues/fullSC/pendingSTM/28mutants; reply/callback trace still required')
