"""Verify the whole original start helper and actual LAB128 read, not cached endpoint state."""
from pathlib import Path
import ast
import base64
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_es_di_ticket_dolphin.py')
body = parent.read_text().split('data, old =', 1)[0].replace('dolphin-es-di-ticket', 'dolphin-playrecord-start').replace(
    'build_es_di_ticket_dolphin.py', 'build_playrecord_start_dolphin.py').replace(
    'run_es_di_ticket_disc_dolphin.ps1', 'run_playrecord_start_disc_dolphin.ps1').replace(
    'prepare_es_di_ticket_disc.py', 'prepare_playrecord_start_disc.py').replace('== 188', '== 532').replace('0x240', '0x380')
tree = ast.parse(Path('experiments/wii-static-recomp/verify_es_consumption_dolphin.py').read_text())
node = next(node for node in tree.body if isinstance(node, ast.Assign) and any(
    isinstance(target, ast.Name) and target.id == 'extra' for target in node.targets))
extra = ast.literal_eval(node.value)
tree = ast.parse(Path('experiments/wii-static-recomp/verify_es_close_after_consumption_dolphin.py').read_text())
extra += ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.AugAssign) and
    isinstance(node.target, ast.Name) and node.target.id == 'extra'))
extra += '''code.append(branch(call['text'] + len(code) * 4, 0x8021d2a0, True))
pointer(code, 12, 0x806f4280)
code.extend([dform(36, 3, 12, 0), 0x7c0000a6, dform(36, 0, 12, 4)])
for slot, address in [(8,0x80528a40),(12,0x8052ab40),(16,0x8052ab44),(20,0x8052ab48),
    (24,0x8052ab4c),(28,0x8052ab50),(32,0x8052ab54),(36,0x804931d0),(40,0x8052aff8)]:
    pointer(code, 11, address)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 12, slot)])
pointer(code, 3, 0x806f4280)
code.append(dform(14, 4, 0, 64))
code.append(branch(call['text'] + len(code) * 4, 0x80212fd0, True))
'''
marker = 'code.extend([dform(32, 3, 1, 8), dform(32, 0, 1, 20)'
assert body.count(marker) == 1
body = body.replace(marker, extra + marker)
exec(compile(body, str(parent), 'exec'), globals())
assert generation['playrecordParentGeneratorSha256'] == sha(experiment / 'build_es_close_after_consumption_dolphin.py')
initial = base64.b64decode(capture['playrecordStartScalars'])
assert initial == struct.pack('>16I', 0, 0x2032, 1, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0)
buffer = base64.b64decode(capture['playrecordBufferPhysical'])
lab = base64.b64decode(capture['playrecordLabFile'])
lab_path = Path('_scratch/tmp/dolphin-playrecord-start-disc-user/Wii/title/00000001/00000002/data/play_rec.dat')
assert len(buffer) == len(lab) == 128 and buffer == lab == lab_path.read_bytes()
log_path = Path('_scratch/tmp/dolphin-playrecord-start-disc-user/Logs/dolphin.log')
log = log_path.read_text(errors='replace')
assert 'Opening /title/00000001/00000002/data/play_rec.dat (mode 3, fd 4)' in log
assert 'Read(/title/00000001/00000002/data/play_rec.dat, 0x00493120, 128): Result 0' in log
assert 'Seek(/title/00000001/00000002/data/play_rec.dat, 0x00000000, 0): Result 0' in log
assert 'Write(/title/00000001/00000002/data/play_rec.dat' not in log
control_path = root / 'dolphin-es-close-after-consumption-disc/fpr-init-true-dolphin.json'
control = json.loads(control_path.read_text(encoding='utf-8-sig'))
data, prior = base64.b64decode(capture['data']), base64.b64decode(control['data'])
assert len(data) == len(prior) == 16 * 736 and data[:7 * 736] == prior[:7 * 736]
for index in range(7, 16):
    row, old = bytearray(data[index * 736:(index + 1) * 736]), prior[index * 736:(index + 1) * 736]
    assert struct.unpack_from('>I', row, 28)[0] == 0x135e0080
    row[28:32] = old[28:32]
    for offset in (84, 88, 92, 96):
        assert struct.unpack_from('>I', row, offset)[0] == struct.unpack_from('>I', old, offset)[0] + 3
        row[offset:offset + 4] = old[offset:offset + 4]
    assert row == old
for key in ('confPhysical','productPhysical','inquiryPhysical','ticketViewPhysical','ticketScalarsPhysical',
    'consumptionCountPhysical','consumptionScalarsPhysical','closeScalarsPhysical'):
    assert base64.b64decode(capture[key]) == base64.b64decode(control[key])
def check_payload(start, payload):
    assert start == struct.pack('>16I', 0, 0x2032, 1, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0)
    assert payload == lab and len(payload) == 128

check_payload(initial, buffer)
mutants = 0
for blob in (initial, buffer):
    for index in range(len(blob)):
        bad = bytearray(blob)
        bad[index] ^= 1
        try:
            check_payload(bad if blob is initial else initial, bad if blob is buffer else buffer)
        except AssertionError:
            mutants += 1
        else:
            raise AssertionError('Play-record payload mutation accepted')
assert mutants == 192
(output / 'playrecord-start-comparison.json').write_text(json.dumps({
    'result':'ORIGINAL_WHOLE_PLAYRECORD_START_OPEN_READ128_SEEK_LAB_BYTE_MATCH_PASS',
    'verifierSha256':sha(Path(__file__)),'generationSha256':sha(generation_path),'captureSha256':sha(capture_path),
    'logSha256':sha(log_path),'labFileSha256':sha(lab_path),'payloadMutantsRejected':192,
    'limits':['532-byte helper reconstructed instruction-by-instruction; original SDK bytes unchanged.',
        'Whole void __OSStartPlayRecord capture shows initial state1/NAND state2; r3 is opaque, not success status.',
        'Actual IOS mode3/FD4 OPEN,READ128,SEEK0 logged; physical128 buffer equals post-stop LAB128 file, no source write logged.',
        'Physical cached FileInfo is not used as proof of final descriptor/state; callback order and cached endpoints still require original replay trace.',
        'Three new requests explain counters+3 and explicit PPC mailbox0080 change; all other16 controls/full previous buffers retained.',
        'New private LAB profile only, not physical NAND/IOS timing, native callback completion or first screen.']},indent=2)+'\n')
print('PASS whole original play-record start/helper532/initialstate1/OPEN4-READ128-SEEK0/LAB128match/previouscontrols; callback trace NEXT')
