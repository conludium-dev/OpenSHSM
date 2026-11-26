"""Execute original bounded KPAD record-copy/error fragments; opaque data, not complete sample processing."""
from pathlib import Path
import hashlib
import json
import itertools
import platform
import struct
import sys

assert platform.machine() == 'x86_64', 'Use the existing isolated x64 Unicorn setup'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'kpad-record-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
def read(address, size):
    section = next(i for i in range(18) if header[18 + i] <= address
        and address + size <= header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    return dol[offset:offset + size]
facts = [(0x8027B0D0, 0x3B000016), (0x8027B0D8, 0x3B7BFF50),
    (0x8027B138, 0x7F0903A6), (0x8027B1C8, 0x989D005C),
    (0x8027B1CC, 0x987D005F), (0x8027B1D0, 0x981D005D)]
for address, expected in facts:
    assert struct.unpack('>I', read(address, 4))[0] == expected, hex(address)
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
fragments = [(0x8027B130, 0x24), (0x8027B1AC, 0x28), (0x80278450, 0x9C)]
for address, size in fragments:
    uc.mem_write(address, read(address, size))
copies = []
for alignment in [0, 4, 8, 12]:
    for seed in range(8):
        source, destination = 0x80540000 + alignment, 0x80560000 + alignment
        payload = bytes((i * 37 + seed * 19) & 255 for i in range(176))
        uc.mem_write(source - 16, b'\xA5' * 16 + payload + b'\xA5' * 16)
        uc.mem_write(destination - 16, b'\xCD' * 208)
        uc.reg_write(ppc.UC_PPC_REG_26, source)
        uc.reg_write(ppc.UC_PPC_REG_27, destination)
        uc.reg_write(ppc.UC_PPC_REG_24, 22)
        uc.emu_start(0x8027B130, 0x8027B154, count=256)
        assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x8027B154
        assert bytes(uc.mem_read(destination, 176)) == payload
        assert bytes(uc.mem_read(destination - 16, 16)) == b'\xCD' * 16
        assert bytes(uc.mem_read(destination + 176, 16)) == b'\xCD' * 16
        assert bytes(uc.mem_read(source - 16, 208)) == b'\xA5' * 16 + payload + b'\xA5' * 16
        assert uc.reg_read(ppc.UC_PPC_REG_CTR) == 0
        copies.append({'alignment': alignment, 'seed': seed, 'bytes': 176,
            'copyExact': True, 'sourcePreserved': True, 'guardsPreserved': True})
errors = []
for error in [-2, -1, 0, -3]:
    for extended in [0, 1]:
        destination = 0x80560000
        uc.mem_write(destination - 16, b'\xCD' * 208)
        uc.reg_write(ppc.UC_PPC_REG_23, error & 0xFFFFFFFF)
        uc.reg_write(ppc.UC_PPC_REG_31, extended)
        uc.reg_write(ppc.UC_PPC_REG_29, destination)
        uc.emu_start(0x8027B1AC, 0x8027B1D4, count=32)
        expected = bytearray(b'\xCD' * 208)
        if error == -2 and extended:
            expected[16 + 0x5C], expected[16 + 0x5D], expected[16 + 0x5F] = 0xFD, 0xFF, 0
        assert bytes(uc.mem_read(destination - 16, 208)) == bytes(expected)
        assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x8027B1D4
        errors.append({'rawReadError': error, 'extendedFlag': extended,
            'changedOffsets': [0x5C, 0x5D, 0x5F] if error == -2 and extended else [], 'guardsPreserved': True})
buttons = []
for type_id, resetting, previous, raw, extra, ext in itertools.product(
        [0, 1, 2, 16, 17], [0, 1], [0, 0x800, 0xFFFF, 0x10000], [0, 0x800, 0xFFFFFFFF], [0, 0x6000], [0, 1]):
    block = 0x80540000
    uc.mem_write(block, b'\0' * 0x600)
    uc.mem_write(block, struct.pack('>I', previous))
    uc.mem_write(block + 0x60, struct.pack('>III', 0x10001, 0xAABBCCDD, 0xAABBCCDD))
    uc.mem_write(block + 0x555, bytes([resetting]))
    for register, value in [(ppc.UC_PPC_REG_3, block), (ppc.UC_PPC_REG_4, type_id),
        (ppc.UC_PPC_REG_6, raw), (ppc.UC_PPC_REG_7, extra), (ppc.UC_PPC_REG_8, ext)]:
        uc.reg_write(register, value)
    uc.emu_start(0x80278450, 0x802784EC, count=128)
    held = raw & 0x9FFF
    if type_id == 1 and resetting == 0:
        held |= extra & 0x6000
    old = previous & 0xFFFF
    expected = (held, held & ~old, old & ~held)
    actual = struct.unpack('>III', uc.mem_read(block, 12))
    assert actual == expected and uc.reg_read(ppc.UC_PPC_REG_PC) == 0x802784EC
    expected_extension = ((ext if resetting == 0 else 0) & 0xFFFF)
    if type_id in (2, 16, 17):
        assert struct.unpack('>III', uc.mem_read(block + 0x60, 12)) == (
            expected_extension, expected_extension & ~1, 1 & ~expected_extension)
    else:
        assert struct.unpack('>III', uc.mem_read(block + 0x60, 12)) == (0x10001, 0xAABBCCDD, 0xAABBCCDD)
    buttons.append({'type': type_id, 'resetFlag': resetting, 'previous': previous,
        'raw': raw, 'extra': extra, 'extension': ext, 'heldTriggerRelease': actual})
report = {'result': 'ORIGINAL_KPAD_OPAQUE_RECORD_FRAGMENTS_PASS', 'dolSha256': sha(dol_path),
    'recipeSha256': sha(Path(__file__)), 'copies': copies, 'errors': errors, 'buttonCases': buttons,
    'fragments': {f'{a:08X}': hashlib.sha256(read(a, size)).hexdigest() for a, size in fragments},
    'instructionFacts': [{'address': f'{a:08X}', 'opcode': f'{b:08X}'} for a, b in facts],
    'limits': ['Original software750CL fragments only, stopped before outer loop/ABI cleanup; no supplied host services or skipped instructions.',
        'Record size176/copy boundary and separate button-edge fields verified; IR/acceleration/extension axes not recovered by copying.',
        'Button fragment stops BEFORE SDK repeat-timer tail802782B0; bit31 repeat behavior is source-only and final button words not fully verified.',
        'Error fragment flags are supplied. Full KPADRead readiness/queue/sampling/count/lifecycle not executed.',
        'Default wrapper8027AAC0 sets extendedflagR7=0, so this error path need not populate output bytes.',
        'No native adapter integration/game run/physical-controller acceptance.']}
(output / 'original-fragments.json').write_text(json.dumps(report, indent=2) + '\n')
print('ORIGINAL_KPAD_OPAQUE_RECORD_FRAGMENTS_PASS', len(copies), 'copy cases', len(errors), 'error cases', len(buttons), 'button cases')
