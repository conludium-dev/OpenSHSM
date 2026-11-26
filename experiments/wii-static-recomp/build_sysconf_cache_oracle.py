"""Snapshot original parsed cached buffers before the final completion marker, replaying it."""
from pathlib import Path
import ast
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_sysconf_product_oracle.py')], check=True)
base = root / 'dolphin-sysconf-long'
output = root / 'dolphin-sysconf-cache-oracle'
output.mkdir(exist_ok=True)
image = bytearray((base / 'fpr-init.dol').read_bytes())
layout = list(struct.unpack('>64I', image[:256]))
helpers = experiment / 'build_dolphin_probe.py'
namespace = {}
for node in ast.parse(helpers.read_text()).body:
    if isinstance(node, ast.FunctionDef):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(helpers), 'exec'), namespace)
dform, pointer, branch, spr = (namespace[name] for name in ('dform', 'pointer', 'branch', 'spr'))
main = next(i for i in range(7) if layout[18 + i] == 0x80600000)
words = list(struct.unpack_from('>' + str(layout[36 + main] // 4) + 'I', image, layout[main]))
matches = [i for i, word in enumerate(words) if word == dform(36, 0, 30, 16)]
assert len(matches) == 16
index = matches[-1]
site = 0x80600000 + index * 4
offset = layout[main] + index * 4
text, data = 0x806c0000, 0x806f0000
code = [dform(36, 0, 1, -32), dform(36, 3, 1, -28), dform(36, 11, 1, -24), dform(36, 12, 1, -20),
    0x7c000026, dform(36, 0, 1, -16), 0x7c0000a6, dform(36, 0, 1, -12), spr(0, 9), dform(36, 0, 1, -8)]
code.extend([dform(32, 0, 1, -12), (21 << 26) | (11 << 16) | (17 << 6) | (15 << 1),
    (31 << 26) | (11 << 21) | (146 << 1)])
loops = []
for source, destination, size in [(0x804b31a0, data + 64, 0x4000), (0x80003800, data + 64 + 0x4000, 256)]:
    pointer(code, 11, source)
    pointer(code, 3, destination)
    pointer(code, 12, size // 32)
    code.append(spr(12, 9, True))
    start = text + len(code) * 4
    for byte in range(0, 32, 4):
        code.extend([dform(32, 0, 11, byte), dform(36, 0, 3, byte)])
    code.extend([0x7c0018ac, dform(14, 11, 11, 32), dform(14, 3, 3, 32)])
    end = text + len(code) * 4
    code.append((16 << 26) | (16 << 21) | ((start - end) & 0xfffc))
    loops.append({'source': source, 'destination': destination, 'bytes': size, 'start': start, 'branch': end})
pointer(code, 11, data | 0x40000000)
code.extend([dform(14, 0, 0, 1), dform(36, 0, 11, 16)])
restore = text + len(code) * 4
code.extend([dform(32, 0, 1, -8), spr(0, 9, True), dform(32, 0, 1, -16), (31 << 26) | (255 << 12) | (144 << 1),
    dform(32, 3, 1, -28), dform(32, 11, 1, -24), dform(32, 12, 1, -20), dform(32, 0, 1, -12),
    (31 << 26) | (146 << 1), dform(32, 0, 1, -32), dform(36, 0, 30, 16)])
code.append(branch(text + len(code) * 4, site + 4))
shadow = bytearray(64 + 0x4000 + 256)
shadow[:16] = b'OSHSM_SC_CACHE01'
for is_text, address, payload in [(True, text, struct.pack('>' + 'I' * len(code), *code)), (False, data, shadow)]:
    slot = next(i for i in (range(7) if is_text else range(7, 18)) if not layout[36 + i])
    layout[slot], layout[18 + slot], layout[36 + slot] = len(image), address, len(payload)
    image.extend(payload)
struct.pack_into('>I', image, offset, branch(site, text))
image[:256] = struct.pack('>64I', *layout)
(output / 'fpr-init.dol').write_bytes(image)
(output / 'generation.json').write_text(json.dumps({'generatorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'helperSha256': hashlib.sha256(helpers.read_bytes()).hexdigest(),
    'controlGenerationSha256': hashlib.sha256((base / 'generation.json').read_bytes()).hexdigest(),
    'harnessSha256': hashlib.sha256(image).hexdigest(), 'site': site, 'offset': offset, 'opcode': dform(36, 0, 30, 16),
    'textAddress': text, 'dataAddress': data, 'restore': restore, 'loops': loops,
    'limits': ['Read-only original cached buffers after final status; EE masked and GPR0/3/11/12/CR/MSR/CTR saved/restored, marker replayed.',
        'Extra reads/scratch stack/shadow flushes/observer timing are laboratory instrumentation, not cycle equivalence.']}, indent=2) + '\n')
print('Prepared original parsed cached-conf16384/product256 snapshot before final marker; no source/data/status replacement')
