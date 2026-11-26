"""Verify whole original ticket-view call and derivation from own Wii ticket."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'dolphin-es-di-ticket-disc'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation_path = root / 'dolphin-es-di-ticket/generation.json'
generation = json.loads(generation_path.read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
control_path = root / 'dolphin-di-burst-disc/fpr-init-true-dolphin.json'
control = json.loads(control_path.read_text(encoding='utf-8-sig'))
assert generation['generatorSha256'] == sha(experiment / 'build_es_di_ticket_dolphin.py')
assert generation['ticketParentGeneratorSha256'] == sha(experiment / 'build_di_burst_dolphin.py')
assert generation['wrapperSha256'] == capture['scriptSha256'].lower() == sha(experiment / 'run_es_di_ticket_disc_dolphin.ps1')
assert generation['harnessSha256'] == capture['harnessSha256'].lower() == sha(output / 'DATA/sys/main.dol')
preparation = json.loads((output / 'preparation.json').read_text())
assert preparation['preparerSha256'] == sha(experiment / 'prepare_es_di_ticket_disc.py')
assert preparation['harnessSha256'] == generation['harnessSha256']
assert capture['emulatorSha256'].lower() == control['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert capture['records'] == 16 and capture['accurateCache'] == 'True'
namespace = {}
helper = experiment / 'build_dolphin_probe.py'
for node in ast.parse(helper.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helper), 'exec'), namespace)
dform, pointer, branch, spr = (namespace[name] for name in ('dform', 'pointer', 'branch', 'spr'))
image = (output / 'DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', image[:256])
original = (root / 'dolphin-di-initialized/fpr-init.dol').read_bytes()
baseline = bytearray(original)
for offset in [generation['burst']['firstOffset'], generation['di86Call']['offset'], generation['di86Call']['offset'] + 16]:
    baseline[offset:offset + 4] = image[offset:offset + 4]
assert image[256:len(original)] == baseline[256:]
call = generation['di86Call']
code = [dform(37, 1, 1, -16), spr(0, 8), dform(36, 0, 1, 20)]
pointer(code, 0, 0x2032)
code.append(0x7c000124)
for register, value in [(3, 0x80492280), (4, 0x80492260), (5, 0x80211060)]:
    pointer(code, register, value)
code.append(branch(call['text'] + len(code) * 4, 0x80223a50, True))
code.extend([dform(36, 3, 30, 408), 0x7c0000a6, dform(36, 0, 30, 412)])
code.append(branch(call['text'] + len(code) * 4, 0x80249790, True))
code.extend([dform(36, 3, 1, 8), dform(14, 3, 0, 0)])
pointer(code, 4, 0x806f4000)
code.append(branch(call['text'] + len(code) * 4, 0x80249a00, True))
pointer(code, 12, 0x806f4200)
code.extend([dform(36, 3, 12, 0), 0x7c0000a6, dform(36, 0, 12, 4)])
for address, size in [(0x806f4000, 216), (0x806f4200, 8)]:
    pointer(code, 3, address)
    code.append(dform(14, 4, 0, size))
    code.append(branch(call['text'] + len(code) * 4, 0x80212fd0, True))
code.extend([dform(32, 3, 1, 8), dform(32, 0, 1, 20), spr(0, 8, True), dform(14, 1, 1, 16), 0x4e800020])
assert call['resume'] == call['text'] + len(code) * 4
code.append(dform(36, 0, 1, -4))
pointer(code, 0, 0xa032)
code.extend([0x7c000124, dform(32, 0, 1, -4), call['replayedWord']])
code.append(branch(call['text'] + len(code) * 4, call['site'] + 20))
slot = call['slot']
assert call['bytes'] == len(code) * 4 == 188
assert image[layout[slot]:layout[slot] + call['bytes']] == struct.pack('>' + 'I' * len(code), *code)
lab = generation['ticketOracle']['sectionSlot']
assert (layout[18 + lab], layout[36 + lab]) == (0x806f4000, 0x240)
assert image[layout[lab]:layout[lab] + 0x240] == bytes(0x240)
data, old = (base64.b64decode(item['data']) for item in (capture, control))
assert len(data) == len(old) == 16 * 736
assert data[:7 * 736] == old[:7 * 736]
for index in range(7, 16):
    row, prior = bytearray(data[index * 736:(index + 1) * 736]), old[index * 736:(index + 1) * 736]
    for offset in (84, 88, 92, 96):
        assert struct.unpack_from('>I', row, offset)[0] == struct.unpack_from('>I', prior, offset)[0] + 1
        row[offset:offset + 4] = prior[offset:offset + 4]
    assert row == prior
for key in ('confPhysical', 'productPhysical', 'inquiryPhysical'):
    assert base64.b64decode(capture[key]) == base64.b64decode(control[key])
ticket_path = Path('work/private-game/disc/DATA/ticket.bin')
ticket = ticket_path.read_bytes()
assert len(ticket) == 676 and ticket[:4] == struct.pack('>I', 0x10001) and ticket[0x1bc] == 0
assert ticket[0x1dc:0x1e4] == Path('work/private-game/disc/DATA/tmd.bin').read_bytes()[0x18c:0x194]
expected = bytes([ticket[0x1bc], 0, 0, 0]) + ticket[0x1d0:0x2a4]
view = base64.b64decode(capture['ticketViewPhysical'])
scalars = base64.b64decode(capture['ticketScalarsPhysical'])


def check(payload, result):
    assert result == struct.pack('>2I', 0, 0x2032)
    assert payload == expected and len(payload) == 216


check(view, scalars)
for blob, size in [(view, 216), (scalars, 8)]:
    for index in range(size):
        changed = bytearray(blob)
        changed[index] ^= 1
        try:
            check(changed if size == 216 else view, changed if size == 8 else scalars)
        except AssertionError:
            pass
        else:
            raise AssertionError('Ticket-view/scalar mutant accepted')
ghidra_path = root / 'es-di-ticket-source/ghidra/verification.json'
ghidra = json.loads(ghidra_path.read_text())
assert ghidra['records'][0]['instructions'] == 41 and ghidra['records'][0]['bytes'] == ghidra['records'][0]['discoveredBodyBytes'] == 164
(output / 'ticket-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_DI_TICKET_VIEW_API0_OWN_TICKET216_GHIDRA_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(generation_path),
    'captureSha256': sha(capture_path), 'ticketSha256': sha(ticket_path), 'viewSha256': hashlib.sha256(view).hexdigest(),
    'mutantsRejected': 224, 'ghidraSha256': sha(ghidra_path),
    'sources': ['Original Wii SDK call/capture', 'Own Wii ticket/TMD bytes', 'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/ES/Formats.cpp'],
    'limits': generation['limits'] + ['CapturedAPI0/2032/full216 equals own ticket version+tail, no key decryption/private-console requirement.',
        'One extra completed request explains exact+1 four queue counters; all other16records/fullfiles unchanged.',
        'No signature cryptography/physical Wii/other regions/native IOCTLV completion verified.']}, indent=2) + '\n')
print('PASS whole original ticket-view API0-2032/full216 equals own Wii ticket/188byte ABI helper/SDK unchanged/queue+1/224mutants/Ghidra41-164')
