"""Replay actual captured decimal-multiply inputs; do not inject state into retail boot."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import struct
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
args = parser.parse_args()
assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, ppc_const as ppc

root = Path('work/private-game/static-recomp/stock-baseline')
output = root / 'window-locked-cache'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
capture_path = root / 'window-lc-numeric' / ('audit-' + args.tag + '.json')
capture = json.loads(capture_path.read_text())
records = [row for row in capture['records'] if row['event'] == 'call' and row['subject'] == 0x8019734C]
assert records and all(all(memory != '-' for memory in row['memory']) for row in records)
for row in records:
    image = {}
    for address, memory in zip(row['gpr'][3:6], row['memory']):
        for offset, value in enumerate(bytes.fromhex(memory)):
            assert address + offset not in image or image[address + offset] == value
            image[address + offset] = value
    assert all(1 <= bytes.fromhex(memory)[4] <= 36 for memory in row['memory'][1:])
request = ''.join(' '.join(map(str, row['gpr'] + [row['ctr'], row['xer'], row['msr'], row['cr']]))
    + ' ' + ' '.join(row['memory']) + '\n' for row in records)
exe = output / 'division-probe'
build = json.loads((output / 'division-build.json').read_text())
assert sha(exe) == build['executableSha256']
assert sha(Path('experiments/wii-static-recomp/stock_division_probe.cpp')) == build['sourceSha256']
native = subprocess.run([str(exe.resolve()), '--replay-multiply'], input=request, capture_output=True, text=True, timeout=30)
(output / ('replay-' + args.tag + '-native.log')).write_text(native.stdout + native.stderr)
assert native.returncode == 0, native.stderr[-2000:]
lines = [line.split() for line in native.stdout.splitlines()]
assert len(lines) == len(records) and all(len(line) == 38 for line in lines)
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
header = struct.unpack('>64I', dol[:256])
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
uc.mem_map(0x90000000, 64 * 1024 * 1024)
for i in range(18):
    if header[36 + i]:
        uc.mem_write(header[18 + i], dol[header[i]:header[i] + header[36 + i]])
registers = [getattr(ppc, f'UC_PPC_REG_{i}') for i in range(32)]
specials = [ppc.UC_PPC_REG_PC, ppc.UC_PPC_REG_LR, ppc.UC_PPC_REG_CTR, ppc.UC_PPC_REG_XER, ppc.UC_PPC_REG_CR]
mismatches = []
for index, (record, line) in enumerate(zip(records, lines)):
    for address, memory in zip(record['gpr'][3:6], record['memory']):
        uc.mem_write(address, bytes.fromhex(memory))
    for register, value in zip(registers, record['gpr']):
        uc.reg_write(register, value)
    uc.reg_write(ppc.UC_PPC_REG_CTR, record['ctr'])
    uc.reg_write(ppc.UC_PPC_REG_CR, record['cr'])
    uc.reg_write(ppc.UC_PPC_REG_MSR, 0)
    uc.reg_write(registers[0], record['xer'])
    uc.mem_write(0x80008000, struct.pack('>I', 0x7C0103A6))
    uc.emu_start(0x80008000, 0x80008004, count=1)
    uc.reg_write(registers[0], record['gpr'][0])
    uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F0000)
    uc.emu_start(0x8019734C, 0x807F0000, count=200000)
    original = [uc.reg_read(register) for register in registers + specials]
    assert original[32] == 0x807F0000
    uc.mem_write(0x807F0000, struct.pack('>I', 0x7C0102A6))
    uc.emu_start(0x807F0000, 0x807F0004, count=1)
    original[35] = uc.reg_read(registers[0])
    memory = bytes(uc.mem_read(record['gpr'][3], 64))
    current = list(map(int, line[1:]))
    if current != original or bytes.fromhex(line[0]) != memory:
        mismatches.append({'index': index, 'differentFields': [i for i in range(37) if current[i] != original[i]],
            'memoryEqual': bytes.fromhex(line[0]) == memory})
report = {'result': 'ACTUAL_CAPTURE_MULTIPLY_REPLAY_PASS' if not mismatches else 'MISMATCH',
    'cases': len(records), 'mismatches': mismatches, 'captureSha256': sha(capture_path),
    'executableSha256': sha(exe), 'dolSha256': sha(dol_path), 'scriptSha256': sha(Path(__file__)),
    'limits': ['Captured native boot inputs replayed against original PPC; not original Wii inputs/reference trace.',
        'Flat Unicorn memory/MSR0, sentinel LR and no interrupts; does not verify original BAT/IRQ/context scheduling.']}
(output / ('replay-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], len(records), 'actual captured inputs;', len(mismatches), 'mismatches')
if mismatches:
    print(mismatches[0])
    sys.exit(1)
