"""Compare the entire unchanged __div2u with original PPC execution, not a host replacement."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import random
import struct
import subprocess
import sys
import argparse
import re

parser = argparse.ArgumentParser()
parser.add_argument('--decimal', action='store_true')
parser.add_argument('--multiply', action='store_true')
parser.add_argument('--carry', action='store_true')
parser.add_argument('--locked-cache', action='store_true')
parser.add_argument('--quantization', action='store_true')
args = parser.parse_args()
assert not (args.decimal and args.multiply)
assert not args.locked_cache or args.carry
assert not args.quantization or args.locked_cache
label = 'multiply' if args.multiply else 'decimal' if args.decimal else 'division'

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
import unicorn
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, ppc_const

root = Path('work/private-game/static-recomp/stock-baseline') / ('window-hid2-carry' if args.carry else 'window-hid2')
if args.locked_cache:
    root = root.parent / 'window-locked-cache'
if args.quantization:
    root = root.parent / 'window-quantization'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((root / 'division-build.json').read_text())
exe = root / 'division-probe'
assert sha(exe) == build['executableSha256']
assert sha(Path('experiments/wii-static-recomp/stock_division_probe.cpp')) == build['sourceSha256']
samples = [0, 1, 9, 10, 11, 0xFFFFFFFF, 0x100000000, 0x100000001,
    0x7FFFFFFFFFFFFFFF, 0x8000000000000000, 0xFFFFFFFFFFFFFFFF]
cases = list(itertools.product(samples, samples[1:]))
random_source = random.Random(0x5348534D)
cases += [(random_source.getrandbits(64), 10) for _ in range(128)]
cases += [(random_source.getrandbits(64), random_source.getrandbits(64) or 1) for _ in range(128)]
if args.decimal:
    cases = [(a, 1) for a in samples] + [(random_source.getrandbits(64), 1) for _ in range(256)]
result = subprocess.run([str(exe.resolve()), *(['--multiply'] if args.multiply else ['--decimal'] if args.decimal else [])], input=''.join(f'{a} {b}\n' for a, b in cases),
    capture_output=True, text=True, timeout=30)
(root / (label + '-native.log')).write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
memory_rows = [bytes.fromhex(line.split()[0]) for line in result.stdout.splitlines()] if args.decimal or args.multiply else []
rows = [list(map(int, line.split()[1:] if args.decimal or args.multiply else line.split())) for line in result.stdout.splitlines()]
assert len(rows) == len(cases) and all(len(row) == 37 for row in rows)
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
header = struct.unpack('>64I', dol[:256])
parent_build = json.loads((root / 'build.json').read_text())
assert sha(root / 'build.json') == build['parentBuildSha256']
optimized = root.parent / 'window-optimized'
optimized_build = json.loads((optimized / 'build.json').read_text())
checked_words = 0
for address, size, module in [(0x801A68D4, 0xEC, 31), (0x801A6AF8, 0xE4, 31),
    (0x80197270, 0xDC, 30), (0x8019734C, 0x288, 30)]:
    source = optimized / f'output_{module}.cpp'
    metadata = next(item for item in optimized_build['modules'] if item['index'] == module)
    assert sha(source) == metadata['sourceSha256']
    obj = optimized / f'output_{module}.cpp.o'
    lowering = json.loads(((root.parent / 'window-hid2-carry' if args.locked_cache else root) / 'lowering.json').read_text())
    lowered = next((item for item in lowering['files'] if item['file'] == source.name), None)
    if args.locked_cache:
        item = next(item for item in parent_build['compiled'] if item['object'] == obj.name)
        lowered = {'objectSha256': item['objectSha256'], 'sourceSha256': item['sourceSha256']}
    if lowered:
        obj = root / obj.name
        assert sha(obj) == lowered['objectSha256']
        assert sha(root / source.name) == lowered['sourceSha256']
    else:
        assert sha(obj) == metadata['objectSha256'] == parent_build['retainedObjects'][str(obj.resolve())]
    text = source.read_text()
    start = text.index(f'void func_{address:08X}(')
    end = text.find('\nvoid func_', start + 1)
    if lowered:
        current = (root / source.name).read_text()
        current_start = current.index(f'void func_{address:08X}(')
        current_end = current.find('\nvoid func_', current_start + 1)
        expected_body = text[start:end]
        if args.carry:
            from carry_lowering import lower as lower_carry
            expected_body, _ = lower_carry(expected_body, dol, stock=True)
        assert current[current_start:current_end] == expected_body
    words = [(int(a, 16), int(w, 16)) for a, w in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', text[start:end])]
    assert [a for a, _ in words] == list(range(address, address + size, 4))
    for a, w in words:
        section = next(i for i in range(18) if header[18 + i] <= a < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + a - header[18 + section])[0] == w
    checked_words += len(words)
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc_const.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for i in range(18):
    if header[36 + i]:
        uc.mem_write(header[18 + i], dol[header[i]:header[i] + header[36 + i]])
registers = [getattr(ppc_const, f'UC_PPC_REG_{i}') for i in range(32)]
specials = [ppc_const.UC_PPC_REG_PC, ppc_const.UC_PPC_REG_LR, ppc_const.UC_PPC_REG_CTR,
    ppc_const.UC_PPC_REG_XER, ppc_const.UC_PPC_REG_CR]
mismatches = []
xer_api_mismatches = 0
for index, ((a, b), native) in enumerate(zip(cases, rows)):
    for i, register in enumerate(registers):
        uc.reg_write(register, 0x11110000 + i)
    for register, value in [(registers[1], 0x80020000), (registers[3], a >> 32),
        (registers[4], a & 0xFFFFFFFF), (registers[5], b >> 32), (registers[6], b & 0xFFFFFFFF),
        (ppc_const.UC_PPC_REG_LR, 0x807F0000), (ppc_const.UC_PPC_REG_CTR, 0x12345678),
        (ppc_const.UC_PPC_REG_XER, 0), (ppc_const.UC_PPC_REG_CR, 0), (ppc_const.UC_PPC_REG_MSR, 0)]:
        uc.reg_write(register, value)
    uc.mem_write(0x80008000, struct.pack('>I', 0x7C0103A6))
    uc.reg_write(registers[0], 0)
    uc.emu_start(0x80008000, 0x80008004, count=1)
    uc.reg_write(registers[0], 0x11110000)
    if args.decimal or args.multiply:
        uc.reg_write(registers[3], 0x80009000)
        uc.reg_write(registers[4], 0x11110004)
        uc.reg_write(registers[5], a >> 32)
        uc.reg_write(registers[6], a & 0xFFFFFFFF)
        uc.mem_write(0x80009000, bytes([0xA5]) * 64)
        uc.mem_write(0x80020000 - 96, bytes([0xCC]) * 112)
    if args.multiply:
        for operand, value in enumerate((a, b)):
            digits = str(value)
            data = bytearray([0xA5] * 64)
            data[0] = 0
            struct.pack_into('>H', data, 2, len(digits) - 1)
            data[4] = len(digits)
            data[5:5 + len(digits)] = bytes(int(digit) for digit in digits)
            uc.mem_write(0x80009200 + operand * 0x200, bytes(data))
        uc.reg_write(registers[4], 0x80009200)
        uc.reg_write(registers[5], 0x80009400)
        uc.reg_write(registers[6], b & 0xFFFFFFFF)
    uc.emu_start(0x8019734C if args.multiply else 0x80197270 if args.decimal else 0x801A68D4, 0x807F0000, count=200000)
    original = [uc.reg_read(register) for register in registers + specials]
    uc.mem_write(0x807F0000, struct.pack('>I', 0x7C0102A6))
    uc.emu_start(0x807F0000, 0x807F0004, count=1)
    observed_xer = uc.reg_read(registers[0])
    xer_api_mismatches += int(observed_xer != original[35])
    original[35] = observed_xer
    assert original[32] == 0x807F0000
    memory_equal = True
    if args.decimal or args.multiply:
        memory = bytes(uc.mem_read(0x80009000, 64))
        memory_equal = memory_rows[index] == memory
        if args.decimal and a:
            assert ''.join(str(digit) for digit in memory[5:5 + memory[4]]) == str(a)
    else:
        assert (original[3] << 32) | original[4] == a // b
    if native != original or not memory_equal:
        mismatches.append({'index': index, 'numerator': a, 'denominator': b,
            'native': native, 'original': original,
            'differentFields': [i for i in range(37) if native[i] != original[i]], 'memoryEqual': memory_equal})
report = {'result': 'MISMATCH' if mismatches else ('WHOLE_DECIMAL_MULTIPLY_ORIGINAL_PPC_PASS' if args.multiply else 'WHOLE_UINT64_DECIMAL_ORIGINAL_PPC_PASS' if args.decimal else 'WHOLE_DIV2U_ORIGINAL_PPC_PASS'), 'cases': len(cases),
    'mismatches': mismatches, 'executableSha256': sha(exe), 'dolSha256': sha(dol_path),
    'nativeLogSha256': sha(root / (label + '-native.log')), 'oracleVersion': unicorn.__version__,
    'verificationScriptSha256': sha(Path(__file__)), 'buildSha256': sha(root / 'division-build.json'),
    'xerApiReadbackMismatches': xer_api_mismatches,
    'originalWordsChecked': checked_words,
    'limits': ['Unicorn750CL original integer execution; not Dolphin IRQ/context, physical Wii or full numeric conversion.',
        'All GPR/PC/LR/CTR/XER/CR compared, no guest scheduling or full boot evidence.',
        'XER initialized/observed using synthetic PPC mtxer/mfxer, following existing carry oracle; API-only readback is inconsistent.']}
(root / (label + '-comparison.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], len(cases), 'whole-function cases;', len(mismatches), 'mismatches')
if mismatches:
    first = mismatches[0]
    print(json.dumps({'index': first['index'], 'differentFields': first['differentFields'],
        'nativeXer': first['native'][35], 'originalXer': first['original'][35], 'memoryEqual': first['memoryEqual']}))
    sys.exit(1)
