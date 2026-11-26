"""Admit the observed packet flush through the same existing quiescent syscall profile."""
from pathlib import Path
import hashlib
import json
import re
import struct

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
parent = experiment / 'build_flush_ee_profile.py'
body = parent.read_text().replace('flush-ee-profile', 'flush-packet-profile')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = root / 'flush-packet-profile'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
layout = struct.unpack('>64I', dol[:256])
def word(address):
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    return struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0]
assert word(0x80242234) == 0x7f83e378
assert word(0x80242238) == 0x38800020
opcode = word(0x8024223c)
assert opcode == 0x4bfd0d95
displacement = opcode & 0x03fffffc
if displacement & 0x02000000:
    displacement -= 0x04000000
assert 0x8024223c + displacement == 0x80212fd0 and opcode & 1 and not opcode & 2
base = root / 'mass-ipc-startup-boot'
build = json.loads((base / 'build.json').read_text())
flush = next(row for row in build['records'] if row['file'] == 'output_63.cpp')
source = Path(flush['source']).read_text().split('void func_80212FD0(CPUContext& ctx) {', 1)[1].split('\nvoid func_', 1)[0]
opcodes = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', source)
assert len(opcodes) == 12
assert all(word(int(address, 16)) == int(value, 16) for address, value in opcodes)
lr_lines = [line.strip() for line in source.splitlines() if 'ctx.lr' in line and 'std::cout' not in line]
assert len(lr_lines) == 2 and all('ctx.pc = ctx.lr; return;' in line for line in lr_lines)
ghidra_path = root / 'dolphin-flush-syscall/ghidra/verification.json'
ghidra = json.loads(ghidra_path.read_text())
for row in ghidra['records']:
    assert row['discoveredBodyBytes'] == row['bytes']
    assert row['objectSha256'] == sha(root / 'dtk-output/obj/auto_03_802045CC_text.o')
    assert row['assemblySha256'] == sha(ghidra_path.parent / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(ghidra_path.parent / (row['name'] + '.c'))
observed = json.loads((root / 'mass-flush-packet-observer/observation.json').read_text())
assert observed['logSha256'] == sha(root / 'mass-flush-packet-observer/observed-boot.log')
assert observed['states'][0] == 'PACKET_FLUSH_STATE 80212fd0 80242240 a032 935e0020 20 c200 0 40f8 0 0 0 0 0 0 0 0 0 0'
header = output / 'flush_syscall.h'
text = header.read_text().replace('inline bool experimentFlushEe = false;',
    'inline bool experimentFlushEe = false;\ninline bool experimentFlushPacket = false;')
text = text.replace('context.lr != 0x8024262c',
    '(context.lr != 0x8024262c && (!experimentFlushPacket || context.lr != 0x80242240))')
header.write_text(text)
(output / 'packet-profile.json').write_text(json.dumps({'builderSha256': sha(Path(__file__)),
    'parentSha256': sha(parent), 'dolSha256': sha(dol_path), 'headerSha256': sha(header),
    'ghidraSha256': sha(ghidra_path), 'observationSha256': sha(root / 'mass-flush-packet-observer/observation.json'),
    'originalBehavior': '80242234/38/3C passes r28,length32 to DCFlushRange; all12function instruction words match DOL.',
    'inferredBehavior': 'LR used only by two returns; changing the fixture caller does not change cache/syscall algorithm.',
    'pcAdaptation': 'Optional second caller in existing quiescent exception gate; no concurrent IRQ permission.'}, indent=2) + '\n')
