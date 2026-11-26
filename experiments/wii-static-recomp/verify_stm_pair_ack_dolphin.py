"""Verify original retained ARM message through later ACKs, independent EEoff sampling."""
from pathlib import Path
import hashlib
import json
import struct

parent = Path('experiments/wii-static-recomp/verify_stm_open_dolphin.py')
prefix = parent.read_text().split('\ndef check(row, case):', 1)[0]
prefix = prefix.replace("startup = '--startup-control' in sys.argv", 'startup = True')
prefix = prefix.replace("name = 'dolphin-stm-open-startup' if startup else 'dolphin-stm-open'", "name = 'dolphin-stm-pair-ack'")
prefix = prefix.replace("wrapper = 'run_stm_open_startup_dolphin.ps1' if startup else 'run_stm_open_dolphin.ps1'", "wrapper = 'run_stm_pair_ack_dolphin.ps1'")
prefix = prefix.replace("experiment / 'build_stm_open_dolphin.py'", "experiment / 'build_stm_pair_ack_dolphin.py'")
prefix = prefix.replace('assert targets == [0x80241c30] * 96', 'assert targets == [0x80241c30] * 66')
exec(compile(prefix, str(parent), 'exec'), globals())
assert generation['ackPairParentSha256'] == sha(experiment / 'build_stm_open_dolphin.py')
assert original_bytes(0x80439904, 19) == b'/dev/stm/eventhook\0'
observations = []
for case in generation['records']:
    i, physical = case['index'], case['physical']
    row = data[i * 736:(i + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>2I', row, 16) == (0xc001cafe, i)
    state = list(struct.unpack_from('>18I', row, 24))
    assert state == [0x30 if i else 0x38, 0, 0x31, 0x32, physical if i else 0, 0x10000,
        0x34, physical, 0x10000, 0x30, 0, 0, 0x14000, 0x2032, physical, 0, physical, case['messageReturn']]
    path = 0x4398f0 if not i % 2 else 0x439904
    packet = struct.pack('>5I', 8, i, 1, path, 0) + bytes(44)
    assert row[192:256] == packet and physical == 0x135e0020 and case['pathAddress'] == path
    observations.append({'index': i, 'states': state, 'packetHex': packet.hex()})
(output / 'comparison.json').write_text(json.dumps({'result': 'ORIGINAL_STM16_ACK_RETAINS_PRIOR_ARM_MESSAGE_PASS',
    'verifierSha256': sha(Path(__file__)), 'generationSha256': sha(output / 'generation.json'), 'captureSha256': sha(capture_path),
    'observations': observations, 'limits': generation['limits']}, indent=2) + '\n')
print('PASS16 original consecutive ACK/reply; later ACK retains previous ARM pointer, not zero')
