"""Compare generated service control flow against original PPC bytes, stopping at unimplemented consumers."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import re
import struct
import subprocess
import sys

assert platform.machine() == 'x86_64', 'PPC Unicorn oracle requires the verified Rosetta/x86-64 runtime'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
import unicorn
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

output = Path('work/private-game/static-recomp/phone-services')
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
sections = [(header[index], header[18 + index], header[36 + index]) for index in range(18) if header[36 + index]]
bounds = {}
for line in (output / 'analyzer-profile.tsv').read_text().splitlines():
    kind, start, end = line.split()
    if kind == 'F':
        bounds[int(start, 16)] = int(end, 16)


def original_word(address):
    offset, base, size = next(row for row in sections if row[1] <= address < row[1] + row[2])
    return struct.unpack_from('>I', dol, offset + address - base)[0]


ir = {}
for line in (output / 'selected-ir.tsv').read_text().splitlines():
    entry, address, opcode = [int(value, 16) for value in line.split()]
    assert entry <= address < bounds[entry] and original_word(address) == opcode
    ir.setdefault(entry, {})[address] = opcode
assert len(ir[0x800ed3c8]) == 320 and len(ir[0x800f3e30]) == 11
assert set(ir[0x800f3e30]) == set(range(0x800f3e30, 0x800f3e5c, 4))
switches = [int(line.split()[1], 16) for line in (output / 'selected-switches.tsv').read_text().splitlines()
            if int(line.split()[0], 16) == 0x800ed3c8]
original_targets = [original_word(0x803f0608 + index * 4) for index in range(31)]
assert set(switches) == set(original_targets) and len(switches) == 18
comments = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', (output / 'selected.cpp').read_text())
assert len(comments) == sum(len(instructions) for instructions in ir.values()) == 477
assert all(original_word(int(address, 16)) == int(opcode, 16) for address, opcode in comments)

entries = [0x800ed3c8, 0x800f3d94, 0x800f3e30, 0x800f3e60, 0x800f3ec0, 0x800ed314]
cases = []
for kind in range(6):
    values = [0, 1, 4, 5] if kind == 1 else [0, 1] if kind == 3 else [0, 50, 100]
    if kind in (0, 2, 5):
        values = [50]
    arguments = list(range(36)) + [0xffffffff] if kind == 0 else list(range(36)) if kind == 5 else [0, 1]
    for value, argument, policy, present, disabled in itertools.product(values, arguments, [0, 1], [0, 1], [0, 1]):
        cases.append((kind, value, argument, policy, present, disabled))
request = ''.join(' '.join(map(str, case)) + '\n' for case in cases)
native_path = output / 'services-host'
result = subprocess.run([str(native_path), str(dol_path)], input=request, capture_output=True, text=True, timeout=90)
(output / 'native-execution.log').write_text(result.stderr)
(output / 'native-snapshots.txt').write_text(result.stdout)
assert result.returncode == 0, (result.returncode, result.stderr[-3000:])
rows = [line.split() for line in result.stdout.splitlines()]
assert len(rows) == len(cases), (len(rows), len(cases))
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for offset, address, size in sections:
    uc.mem_write(address, dol[offset:offset + size])
host, obj, vtable = 0x80600000, 0x80604000, 0x80605000
stack, sentinel, table = 0x80700000, 0x807f0000, 0x80477328
trace = []
external = False


def observe(uc, address, size, _):
    global external
    if not any(start <= address < end for start, end in bounds.items()):
        external = True
        uc.emu_stop()
    else:
        trace.append(address)


uc.hook_add(UC_HOOK_CODE, observe)
records = []
covered_targets = set()
for case, row in zip(cases, rows):
    kind, value, argument, policy, present, disabled = case
    host_data = bytearray(0x3000)
    if present:
        for offset in range(0x1e90, 0x1fa8, 4):
            struct.pack_into('>I', host_data, offset, obj)
    if disabled:
        host_data[0x1fa8:0x1fb0] = bytes([255]) * 8
    uc.mem_write(host, bytes(host_data))
    uc.mem_write(obj, struct.pack('>I', vtable) + bytes(28))
    uc.mem_write(vtable, bytes(16) + struct.pack('>I', 0x807e0000) + bytes(12))
    uc.mem_write(stack - 128, bytes(160))
    uc.mem_write(table, struct.pack('>17I', *[value if index in (4, 7, 16) else 0xabcdef01 for index in range(17)]))
    uc.mem_write(0x80529d20, struct.pack('>I', host))
    uc.mem_write(0x805292f8, struct.pack('>I', host))
    for index in range(32):
        uc.reg_write(getattr(ppc, 'UC_PPC_REG_' + str(index)), 0x12340000 + index * 0x100)
    for index, register_value in [(1, stack), (2, 0x805335e0), (3, host), (4, argument), (5, policy), (13, 0x8052e720)]:
        uc.reg_write(getattr(ppc, 'UC_PPC_REG_' + str(index)), register_value)
    for register, register_value in [(ppc.UC_PPC_REG_CR, 0), (ppc.UC_PPC_REG_XER, 0),
                                      (ppc.UC_PPC_REG_CTR, 0), (ppc.UC_PPC_REG_LR, sentinel)]:
        uc.reg_write(register, register_value)
    external = False
    trace.clear()
    uc.emu_start(entries[kind], sentinel, count=4096)
    pc = uc.reg_read(ppc.UC_PPC_REG_PC)
    assert external or pc == sentinel, (case, hex(pc))
    expected = [int(external), pc, uc.reg_read(ppc.UC_PPC_REG_LR), uc.reg_read(ppc.UC_PPC_REG_CTR), uc.reg_read(ppc.UC_PPC_REG_CR)]
    expected += [uc.reg_read(getattr(ppc, 'UC_PPC_REG_' + str(index))) for index in range(32)]
    expected += list(struct.unpack('>17I', uc.mem_read(table, 68)))
    actual = list(map(int, row[:54]))
    assert actual == expected, (case, [(index, actual[index], expected[index]) for index in range(54) if actual[index] != expected[index]])
    assert row[54] == uc.mem_read(stack - 128, 160).hex(), (case, 'stack bytes mismatch')
    assert row[55] == '1' and uc.mem_read(host, 0x3000) == host_data, (case, 'host state unexpectedly mutated')
    visited_targets = set(trace) & set(original_targets)
    covered_targets |= visited_targets
    records.append({'input': case, 'scope': 'externalConsumerBoundary' if external else 'selectedFunctionReturn',
                    'pc': hex(pc), 'lr': hex(expected[2]), 'r3': expected[8], 'r4': expected[9],
                    'switchTargetsVisited': [hex(address) for address in sorted(visited_targets)],
                    'registersOptionsStackHostMatch': True, 'originalTrace': list(trace)})
assert covered_targets == set(original_targets), (covered_targets, set(original_targets))
report = {'result': 'PASS', 'cases': len(records), 'records': records, 'selectedIrInstructions': 477,
          'jumpTableEntries': 31, 'uniqueJumpTargets': 18, 'allUniqueJumpTargetsExecuted': True,
          'originalDolSha256': hashlib.sha256(dol).hexdigest(), 'generatedSha256': hashlib.sha256((output / 'selected.cpp').read_bytes()).hexdigest(),
          'nativeHostSha256': hashlib.sha256(native_path.read_bytes()).hexdigest(), 'oracleVersion': unicorn.__version__,
          'nativeSnapshotsSha256': hashlib.sha256((output / 'native-snapshots.txt').read_bytes()).hexdigest(),
          'oracleCpu': 'PPC32_750CL_V2_0', 'nativeHostArchitecture': 'ARM64',
          'limits': ['Original selected functions/services only; unimplemented external consumers stop before execution, never return fabricated success.',
                     'Non-null controlled host/object/vtable and suppression flags, not live original audio objects or Wii traces.',
                     'Both full selected-function returns and external-boundary prefixes are reported separately; full ringtone/volume audio remains unverified.',
                     'No pending asynchronous callbacks supplied; no physical rumble, save persistence, new live PhoneUI integration or public release.']}
(output / 'execution.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:', len(records), 'original PPC vs ARM64 service-control cases;18switch targets executed; external consumer boundaries remain explicit')
