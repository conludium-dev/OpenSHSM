"""Check final-marker replay, unchanged whole-SC endpoints and real parsed cached buffers."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'dolphin-sysconf-cache-oracle-disc'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_sysconf_product_oracle.py')], check=True)
generation_path = root / 'dolphin-sysconf-cache-oracle/generation.json'
generation = json.loads(generation_path.read_text())
prep = json.loads((output / 'preparation.json').read_text())
capture_path = output / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
control_path = root / 'dolphin-sysconf-product-oracle-disc/fpr-init-true-dolphin.json'
control = json.loads(control_path.read_text(encoding='utf-8-sig'))
assert generation['generatorSha256'] == sha(experiment / 'build_sysconf_cache_oracle.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert prep['preparerSha256'] == sha(experiment / 'prepare_sysconf_cache_oracle.py')
assert capture['scriptSha256'].lower() == sha(experiment / 'run_sysconf_cache_oracle.ps1')
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == prep['harnessSha256'] == sha(output / 'DATA/sys/main.dol')
assert capture['emulatorSha256'].lower() == control['emulatorSha256'].lower()
assert capture['records'] == 16 and capture['accurateCache'] == 'True'
image = (output / 'DATA/sys/main.dol').read_bytes()
original = (root / 'dolphin-sysconf-long/fpr-init.dol').read_bytes()
baseline = bytearray(original)
offset, site, text, restore = (generation[key] for key in ('offset', 'site', 'textAddress', 'restore'))


def target(address, word):
    assert word >> 26 == 18 and not word & 3
    delta = word & 0x3fffffc
    return address + delta - (0x4000000 if delta & 0x2000000 else 0)


word = struct.unpack_from('>I', image, offset)[0]
assert target(site, word) == text
assert struct.unpack_from('>I', original, offset)[0] == generation['opcode'] == 0x901e0010
struct.pack_into('>I', baseline, offset, word)
assert image[256:len(original)] == baseline[256:]
layout = struct.unpack('>64I', image[:256])
slot = next(i for i in range(7) if layout[18 + i] == text)
code_offset = layout[slot]
words = list(struct.unpack_from('>' + str(layout[36 + slot] // 4) + 'I', image, code_offset))
assert words[:10] == [0x9001ffe0, 0x9061ffe4, 0x9161ffe8, 0x9181ffec, 0x7c000026, 0x9001fff0,
    0x7c0000a6, 0x9001fff4, 0x7c0902a6, 0x9001fff8]
assert words[(restore - text) // 4:-1] == [0x8001fff8, 0x7c0903a6, 0x8001fff0, 0x7c0ff120,
    0x8061ffe4, 0x8161ffe8, 0x8181ffec, 0x8001fff4, 0x7c000124, 0x8001ffe0, 0x901e0010]
assert target(text + (len(words) - 1) * 4, words[-1]) == site + 4
assert words[11:13] == [(21 << 26) | (11 << 16) | (17 << 6) | (15 << 1), 0x7d600124]
for loop in generation['loops']:
    start, branch = loop['start'], loop['branch']
    span = words[(start - text) // 4:(branch - text) // 4 + 1]
    assert len(span) == 20
    for i in range(8):
        assert span[i * 2] == (32 << 26) | (11 << 16) | (i * 4)
        assert span[i * 2 + 1] == (36 << 26) | (3 << 16) | (i * 4)
    assert span[16:19] == [0x7c0018ac, 0x396b0020, 0x38630020]
    assert span[19] == (16 << 26) | (16 << 21) | ((start - branch) & 0xfffc)
    assert loop['bytes'] in (0x4000, 256) and loop['bytes'] % 32 == 0
    def pointer_words(register, value):
        return [(15 << 26) | (register << 21) | (value >> 16),
            (24 << 26) | (register << 21) | (register << 16) | (value & 65535)]
    prefix = words[(start - text) // 4 - 7:(start - text) // 4]
    assert prefix == pointer_words(11, loop['source']) + pointer_words(3, loop['destination']) + pointer_words(12, loop['bytes'] // 32) + [0x7d8903a6]
data, golden = base64.b64decode(capture['data']), base64.b64decode(control['data'])
assert len(data) == len(golden) == 16 * 736
for index in range(5, 16):
    for a, b in [(16, 24), (36, 80), (80, 100), (192, 320), (400, 408), (416, 512), (608, 620), (644, 648), (720, 732)]:
        assert data[index * 736 + a:index * 736 + b] == golden[index * 736 + a:index * 736 + b]
assert capture['confPhysical'] == control['confPhysical'] and capture['productPhysical'] == control['productPhysical']
shadow = base64.b64decode(capture['parsedCache'])
assert len(shadow) == 16704 and shadow[:16] == b'OSHSM_SC_CACHE01' and struct.unpack_from('>I', shadow, 16)[0] == 1
parsed = shadow[64:16448]
physical = base64.b64decode(capture['confPhysical'])
assert parsed[:16308] == physical[:16308] and parsed[16308:16380] != physical[16308:16380]
assert parsed[-4:] == physical[-4:] == b'SCed'
assert shadow[16448:] == base64.b64decode(capture['productPhysical'])
(output / 'verification.json').write_text(json.dumps({'verifierSha256': sha(Path(__file__)),
    'captureSha256': sha(capture_path), 'generationSha256': sha(generation_path), 'controlCaptureSha256': sha(control_path),
    'parsedConfSha256': hashlib.sha256(parsed).hexdigest(),
    'result': 'ORIGINAL_SC_CACHED_INDEX_CAPTURE_REPLAY_CODE_AND_UNOBSERVED_ENDPOINTS_PASS',
    'limits': ['Shadow copy is original cached CPU reads, not IOS file bytes. Added observer timing/scratch/shadow flushes are not cycle equivalence.']}, indent=2) + '\n')
print('PASS original parsed cached-conf16384/index tail/product256/replay-save-restore/11 endpoints;physical file views unchanged')
