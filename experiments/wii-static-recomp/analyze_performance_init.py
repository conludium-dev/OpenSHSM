"""Inventory original performance-register opcodes and the boot reset sequence."""
from pathlib import Path
import hashlib
import json
import struct

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/performance-init')
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
names = {936: 'UMMCR0', 937: 'UPMC1', 938: 'UPMC2', 939: 'USIA',
         940: 'UMMCR1', 941: 'UPMC3', 942: 'UPMC4', 952: 'MMCR0',
         953: 'PMC1', 954: 'PMC2', 955: 'SIA', 956: 'MMCR1', 957: 'PMC3', 958: 'PMC4'}


def read(address, size):
    sections = [index for index in range(18)
                if header[18 + index] <= address and address + size <= header[18 + index] + header[36 + index]]
    assert len(sections) == 1, hex(address)
    index = sections[0]
    offset = header[index] + address - header[18 + index]
    data = dol[offset:offset + size]
    assert len(data) == size
    return data


def spr_instruction(opcode):
    if opcode >> 26 != 31 or ((opcode >> 1) & 1023) not in (339, 467):
        return None
    spr = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
    if spr not in names:
        return None
    return {'spr': spr, 'name': names[spr], 'gpr': (opcode >> 21) & 31,
            'operation': 'write' if ((opcode >> 1) & 1023) == 467 else 'read'}


sites = []
for section in range(7):
    start, size = header[18 + section], header[36 + section]
    for displacement in range(0, size - 3, 4):
        address = start + displacement
        opcode = struct.unpack('>I', read(address, 4))[0]
        decoded = spr_instruction(opcode)
        if decoded:
            sites.append({'address': f'0x{address:08X}', 'opcode': f'0x{opcode:08X}', **decoded})

reset = []
expected = [952, 956, 953, 954, 957, 958]
for index, spr in enumerate(expected):
    address = 0x802113A8 + index * 8
    argument, call = struct.unpack('>II', read(address, 8))
    assert argument == 0x38600000, (hex(address), hex(argument))
    assert call >> 26 == 18 and call & 3 == 1
    displacement = call & 0x03FFFFFC
    if displacement & 0x02000000:
        displacement -= 0x04000000
    target = (address + 4 + displacement) & 0xFFFFFFFF
    setter, return_opcode = struct.unpack('>II', read(target, 8))
    decoded = spr_instruction(setter)
    assert decoded == {'spr': spr, 'name': names[spr], 'gpr': 3, 'operation': 'write'}
    assert return_opcode == 0x4E800020
    reset.append({'argumentAddress': f'0x{address:08X}', 'callAddress': f'0x{address + 4:08X}',
                  'target': f'0x{target:08X}', 'suppliedValue': 0, **decoded,
                  'setterBytesSha256': hashlib.sha256(read(target, 8)).hexdigest()})

live = Path('work/private-game/static-recomp/mass-timebase-active/live-boot.json')
live_report = json.loads(live.read_text())
assert 'BOOT_BOUNDARY pc=80210720 lr=802113b0 msr=2030' in live_report['stdout']
assert reset[0]['target'] == '0x80210720'
report = {'result': 'ORIGINAL_SIX_REGISTER_RESET_STATIC_PATH_IDENTIFIED',
          'evidenceClass': 'Wii original DOL bytes; static path inspection',
          'dolSha256': hashlib.sha256(dol).hexdigest(), 'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'liveReportSha256': hashlib.sha256(live.read_bytes()).hexdigest(),
          'sequenceBytesSha256': hashlib.sha256(read(0x802113A8, 48)).hexdigest(),
          'resetSequence': reset, 'textOpcodeCandidates': sites,
          'referenceSources': ['https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/PowerPC/Gekko.h',
                               'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/PowerPC/Interpreter/Interpreter_SystemRegisters.cpp'],
          'limits': ['Text scan can include data or unreachable code; not a confirmed function catalogue.',
                     'Static sequence supplies zero to MMCR0/MMCR1/PMC1..4; no dynamic acceptance of the entire sequence.',
                     'Register names follow Dolphin reference definitions; physical counters, counting, interrupt and alias semantics remain unverified.',
                     'No runtime lowering or quarantine entries changed; no assertion that subsequent performance-monitor uses can be ignored.',
                     'Full post-timebase boot endpoint, PC clock epoch, menu and game remain unverified.']}
output.mkdir(exist_ok=True)
(output / 'original-analysis.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'Original reset: six zero writes; {len(sites)} performance-register text opcode candidates; runtime unchanged')
