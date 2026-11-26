"""Run original DOL instructions in Unicorn PPC, compare untouched generated native code."""
from pathlib import Path
import hashlib
import itertools
import json
import struct
import subprocess
import sys
import platform

sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/' + ('python-x64' if platform.machine() == 'x86_64' else 'python'))
import unicorn
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

private = Path('work/private-game/static-recomp')
generated = private / 'nwii-current'
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
words = struct.unpack('>64I', dol[:256])
sections = [(words[index], words[18 + index], words[36 + index]) for index in range(18) if words[36 + index]]


def function_bytes(address, size):
    offset, base, length = next(row for row in sections if row[1] <= address and address + size <= row[1] + row[2])
    return dol[offset + address - base:offset + address - base + size]


uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
functions = [(0x800c770c, 20), (0x800c7720, 20), (0x800f3e60, 96)]
for address, size in functions:
    uc.mem_write(address, function_bytes(address, size))
trace = []
uc.hook_add(UC_HOOK_CODE, lambda _, address, size, __: trace.append(address))
table, stack, sentinel = 0x80477328, 0x80100000, 0x80110000
values = list(range(0, 129)) + [0x7ffffffe, 0x7fffffff, 0x80000000, 0xfffffffe, 0xffffffff]
cases = list(itertools.product(values, [0, 1, 2, 0xffffffff]))
request = ''.join(f'{value} {direction}\n' for value, direction in cases)
native = subprocess.run([str(generated / 'probe-host')], input=request, capture_output=True, text=True, timeout=60)
assert native.returncode == 0, (native.returncode, native.stdout[-500:], native.stderr)
rows = [list(map(int, line.split())) for line in native.stdout.splitlines()]
assert len(rows) == len(cases)
records = []
for (value, direction), row in zip(cases, rows):
    assert row[:2] == [value, direction] and row[3:] == [1, 3, 0, 1], row
    uc.mem_write(table, struct.pack('>17I', *([0xabcdef01] * 16 + [value])))
    for index in range(32):
        uc.reg_write(getattr(ppc, 'UC_PPC_REG_' + str(index)), 0x12340000 + index * 0x100)
    before = [uc.reg_read(getattr(ppc, 'UC_PPC_REG_' + str(index))) for index in range(14, 32)]
    uc.reg_write(ppc.UC_PPC_REG_1, stack)
    uc.reg_write(ppc.UC_PPC_REG_4, direction)
    uc.reg_write(ppc.UC_PPC_REG_LR, sentinel)
    trace.clear()
    uc.emu_start(0x800f3e60, sentinel, count=128)
    result = struct.unpack('>I', uc.mem_read(table + 64, 4))[0]
    assert result == row[2], (value, direction, result, row)
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == sentinel and uc.reg_read(ppc.UC_PPC_REG_LR) == sentinel
    assert uc.reg_read(ppc.UC_PPC_REG_1) == stack
    assert [uc.reg_read(getattr(ppc, 'UC_PPC_REG_' + str(index))) for index in range(14, 32)] == before
    assert uc.mem_read(table, 64) == struct.pack('>16I', *([0xabcdef01] * 16))
    assert 0x800c770c in trace and 0x800c7720 in trace
    records.append({'prior': value, 'direction': direction, 'ppcValue': result, 'nativeValue': row[2],
                    'guestAbiPreserved': True, 'nativeAbiPreserved': True, 'nativeTraceCallbacks': row[4],
                    'originalInstructionTrace': list(trace)})
report = {'result': 'PASS', 'cases': len(records), 'records': records, 'oracle': 'Unicorn PPC big-endian original DOL bytes',
          'unicornVersion': unicorn.__version__, 'dolSha256': hashlib.sha256(dol).hexdigest(),
          'oracleHostArchitecture': platform.machine(), 'cpuModel': 'PPC32_750CL_V2_0',
          'generatedSha256': hashlib.sha256((generated / 'selected.cpp').read_bytes()).hexdigest(),
          'librarySha256': hashlib.sha256((generated / 'libshsm-recomp-probe.dylib').read_bytes()).hexdigest(),
          'hostSha256': hashlib.sha256((generated / 'probe-host').read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'limits': ['Synthetic option table and PPC stack, not a full Wii boot, physical-console trace or Gekko paired-single test.',
                     'Actual existing PhoneSettings header participates in native-host test for valid0/1 states; live SDL/game runtime is not linked.',
                     'Trace callback is PC test instrumentation. No original-game HLE replacements or interpreter fallback used.']}
(private / 'execution-unicorn-vs-nwii.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:', len(records), 'original PPC vs compiled native cases, guest/native ABI and host roundtrip')
