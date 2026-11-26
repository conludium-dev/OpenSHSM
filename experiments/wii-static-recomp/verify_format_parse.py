"""Compare the repaired complete parser against original PPC750CL instructions."""
from pathlib import Path
import hashlib
import json
import platform
import struct
import subprocess
import sys

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'format-parse'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
assert build['builderSha256'] == sha(experiment / 'build_format_parse.py')
assert build['lowererSha256'] == sha(experiment / 'format_jump_lowering.py')
for key, name in [('sourceSha256', 'output_50.cpp'), ('objectSha256', 'output_50.cpp.o'), ('hostSha256', 'format-host.cpp'), ('executableSha256', 'format-probe')]:
    assert build[key] == sha(output / name)
assert build['hostSourceSha256'] == sha(experiment / 'format_parse_host.cpp')
assert build['baseExecutionSha256'] == sha(private / 'exi-getid-native/execution.json')
for path, digest in build['sourceHashes'].items():
    assert digest == sha(Path(path))
formats = [b'%' + bytes([character]) + b'TAIL' for character in range(65, 121)]
formats += [b'%sTAIL', b'%lsTAIL', b'%%TAIL', b'%#08xTAIL', b'%+12.3dTAIL', b'%*.*sTAIL', b'%nTAIL']
cases = [(value, ni) for ni in range(2) for value in formats]
inputs = ''.join(value.hex() + ' ' + str(ni) + '\n' for value, ni in cases)
native = subprocess.run([str(output / 'format-probe'), 'work/private-game/disc/DATA/sys/main.dol'], input=inputs, capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0, native.stderr[-2000:]
rows = [list(map(int, line.split()[1:])) for line in native.stdout.splitlines() if line.startswith('FORMAT_CASE ')]
assert len(rows) == len(cases)
assert build['unfixedExecutableSha256'] == sha(output / 'format-unfixed-probe')
unfixed = subprocess.run([str(output / 'format-unfixed-probe'), 'work/private-game/disc/DATA/sys/main.dol'], input=inputs, capture_output=True, text=True, timeout=30)
(output / 'unfixed.log').write_text(unfixed.stdout + unfixed.stderr)
assert unfixed.returncode == 0
unfixed_rows = [list(map(int, line.split()[1:])) for line in unfixed.stdout.splitlines() if line.startswith('FORMAT_CASE ')]
assert len(unfixed_rows) == len(rows)
unfixed_differences = sum(a != b for a, b in zip(rows, unfixed_rows))
assert unfixed_differences > 0
assert all(unfixed_row[0] == 0 for (value, ni), unfixed_row in zip(cases, unfixed_rows) if value == b'%sTAIL')
dispatched = subprocess.run([str(output / 'format-unfixed-probe'), 'work/private-game/disc/DATA/sys/main.dol', 'dispatch'], input=inputs, capture_output=True, text=True, timeout=30)
(output / 'dispatched.log').write_text(dispatched.stdout + dispatched.stderr)
assert dispatched.returncode == 0, dispatched.stderr[-2000:]
dispatch_rows = [list(map(int, line.split()[1:])) for line in dispatched.stdout.splitlines() if line.startswith('FORMAT_CASE ')]
assert dispatch_rows == rows
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for index in range(18):
    if header[36 + index]:
        uc.mem_write(header[18 + index], dol[header[index]:header[index] + header[36 + index]])
regs = [getattr(ppc, f'UC_PPC_REG_{index}') for index in range(32)]
targets_seen = set()
def observe(machine, address, size, unused):
    if address == 0x807f0000:
        machine.emu_stop()
    if address == 0x80199db4:
        targets_seen.add(machine.reg_read(ppc.UC_PPC_REG_CTR))
uc.hook_add(UC_HOOK_CODE, observe)
comparisons = []
for (value, ni), native_row in zip(cases, rows):
    uc.mem_write(0x8053ff80, bytes(256))
    uc.mem_write(0x806a0000, bytes(1024))
    uc.mem_write(0x806a0000, value + b'\0')
    for address, number in [(0x806a0104, 0x806a0300), (0x806a0108, 0x806a0300), (0x806a0300, 7), (0x806a0304, 3)]:
        uc.mem_write(address, struct.pack('>I', number))
    values = [0x11110000 + index for index in range(32)]
    for index, number in [(1, 0x80540000), (2, 0x805335e0), (13, 0x8052e720), (3, 0x806a0000), (4, 0x806a0100), (5, 0x806a0200)]:
        values[index] = number
    for register, number in zip(regs, values):
        uc.reg_write(register, number)
    for register, number in [(ppc.UC_PPC_REG_CR, 0), (ppc.UC_PPC_REG_XER, 0), (ppc.UC_PPC_REG_CTR, 0),
                             (ppc.UC_PPC_REG_LR, 0x807f0000), (ppc.UC_PPC_REG_MSR, 0x2000)]:
        uc.reg_write(register, number)
    uc.emu_start(0x80199a24, 0x807f0004, count=100000)
    expected = [int(uc.reg_read(ppc.UC_PPC_REG_PC) == 0x807f0000)] + [uc.reg_read(register) for register in regs]
    expected += [uc.reg_read(register) for register in (ppc.UC_PPC_REG_CR, ppc.UC_PPC_REG_XER, ppc.UC_PPC_REG_CTR, ppc.UC_PPC_REG_LR)]
    for address, size in [(0x8053ff80, 256), (0x806a0100, 16), (0x806a0200, 16)]:
        expected += list(uc.mem_read(address, size))
    assert expected[0] == 1
    assert native_row == expected, (value, ni, [(i, a, b) for i, (a, b) in enumerate(zip(native_row, expected)) if a != b][:12])
    comparisons.append({'formatHex': value.hex(), 'ni': ni, 'result': 'PASS', 'outputHex': bytes(expected[-16:]).hex()})
assert targets_seen == set(build['changes'][0]['targets']), [hex(value) for value in targets_seen]
(output / 'comparison.json').write_text(json.dumps({'result': 'COMPLETE_PARSE_FORMAT126_CASES_PPC_NATIVE_PASS', 'cases': len(cases),
    'jumpTargetsCovered': sorted(targets_seen), 'buildSha256': sha(build_path), 'originalSha256': sha(dol_path), 'verifierSha256': sha(Path(__file__)),
    'comparisons': comparisons, 'unfixedDifferences': unfixed_differences, 'unmodifiedDispatcherCases': len(dispatch_rows),
    'limits': ['Whole original parser on synthetic format/va-list/output/stack fixtures; NI0/1 native input, PPC oracle flat memory/MSR2000.',
        'Compare32GPR/CR/XER/CTR/LR/return and288stack-va-list-output bytes; no cache/MMIO/FPSCR/printf-rendered text/full OSReport or full game proof.']}, indent=2) + '\n')
print('PASS126 whole parse_format calls/10original jump targets/32GPR-CR-XER-CTR-LR/288bytes')
print('Unfixed generated parser differs in', unfixed_differences, 'cases; string-case premature return detected')
print('PASS126 unmodified parser via existing run_game dispatcher matches original; direct-call exit is a dispatcher handoff')
