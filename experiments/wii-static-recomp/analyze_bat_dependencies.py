"""Inventory original BAT/HID4 access candidates before changing the shared memory frontend."""
from pathlib import Path
import hashlib
import json
import struct

output = Path('work/private-game/static-recomp/dolphin-hid4-probe')
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = original_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
registers = {}
for base, bank, first in [(528, 'IBAT', 0), (536, 'DBAT', 0), (560, 'IBAT', 4), (568, 'DBAT', 4)]:
    for offset in range(8):
        registers[base + offset] = f'{bank}{first + offset // 2}' + ('L' if offset & 1 else 'U')
registers[1011] = 'HID4'
sites = []
for section in range(7):
    for displacement in range(0, header[36 + section] - 3, 4):
        offset = header[section] + displacement
        opcode = struct.unpack_from('>I', dol, offset)[0]
        if opcode >> 26 != 31 or ((opcode >> 1) & 1023) not in (339, 467):
            continue
        ident = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
        if ident in registers:
            sites.append({'address': f'0x{header[18 + section] + displacement:08X}',
                          'opcode': f'0x{opcode:08X}', 'spr': ident, 'name': registers[ident],
                          'operation': 'write' if ((opcode >> 1) & 1023) == 467 else 'read'})
vendor = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/include/runtime/cpu_context.h')
frontend = Path('experiments/wii-static-recomp/memory_frontend.h')
assert 'uint32_t paddr = addr & 0x3FFFFFFF;' in vendor.read_text()
assert 'const uint32_t physical = address & 0x3fffffffu;' in frontend.read_text()
function_address = 0x80210840
section = next(i for i in range(18) if header[18 + i] <= function_address < header[18 + i] + header[36 + i])
offset = header[section] + function_address - header[18 + section]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
live_path = Path('work/private-game/static-recomp/mass-performance/live-boot.json')
live = json.loads(live_path.read_text())
assert 'BOOT_BOUNDARY pc=80210840 lr=802113e0 msr=2030' in live['stdout']
report = {'result': 'HID4_REQUIRES_SHARED_BAT_TRANSLATION_BEFORE_ACTIVATION',
          'originalSha256': sha(original_path), 'functionBytesSha256': hashlib.sha256(dol[offset:offset + 80]).hexdigest(),
          'scriptSha256': sha(Path(__file__)), 'vendorMmuSha256': sha(vendor), 'frontendSha256': sha(frontend),
          'liveReportSha256': sha(live_path), 'opcodeCandidates': sites,
          'bootArgument': '0x83900000', 'bootSbeEnabled': bool(0x83900000 & 0x02000000),
          'referenceSources': ['https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/PowerPC/Gekko.h',
                               'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/PowerPC/Interpreter/Interpreter_SystemRegisters.cpp',
                               'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/PowerPC/MMU.cpp'],
          'limits': ['Original text scan includes candidates, not proven execution or function boundaries.',
                     'Current memory profile strips alias bits; no dynamic BAT banks or HID4 SBE semantics.',
                     'Pure BAT resolver test is separate evidence, not native runtime integration or physical Wii MMU proof.']}
(output / 'dependency-analysis.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'BAT/HID4 dependency:{len(sites)}original text opcode candidates; bootSBE=1, current frontend lacks BAT translation')
