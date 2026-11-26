"""Compare restored scan contracts with original own-DOL PPC execution."""
from pathlib import Path
import hashlib
import json
import platform
import re
import struct
import subprocess
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--continuation-routes', action='store_true')
args = parser.parse_args()
assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / ('window-scan-routes' if args.continuation_routes else 'window-scan-restore')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'probe-build.json').read_text())
assert sha(output / 'build.json') == build['parentBuildSha256']
assert sha(Path('experiments/wii-static-recomp/stock_scan_probe.cpp')) == build['sourceSha256']
assert sha(output / 'scan-probe') == build['executableSha256']
for path, digest in build['linkInputs'].items():
    assert sha(Path(path)) == digest
cases = [(b'#ff112233', b'#%x'), (b'#FF000000', b'#%x'), (b'#FFFFFFFF', b'#%x'),
    (b'123', b'%d'), (b'-42', b'%d'), (b'2147483647', b'%d'), (b'4294967295', b'%u'),
    (b'10 20', b'%u %u'), (b'0xabc', b'%x'), (b'hello', b'%5s'), (b'A', b'%c'),
    (b'abc', b'%d'), (b'', b'%u'), (b'%', b'%%'), (b'12,34', b'%d,%d'),
    (b'1.5', b'%f'), (b'-2.75', b'%lf'), (b'1e-3', b'%f'),
    (b'0,90.618,175.818,90.382', b'%f,%f,%f,%f'),
    (b'00:00:01.200', b'%u:%u:%f')]
request = ''.join((value.hex() or '-') + ' ' + fmt.hex() + '\n' for value, fmt in cases)
dol_path = Path('work/private-game/disc/DATA/sys/main.dol').resolve()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
result = subprocess.run([str(output / 'scan-probe'), str(dol_path)], input=request,
    capture_output=True, text=True, timeout=120)
(output / 'original-compare-native.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout[-2000:] + result.stderr
if args.continuation_routes:
    assert result.stdout.count('SCAN_ROUTES 76\n') == 1
    assert '[Interp]' not in result.stdout + result.stderr
native = re.findall(r'^SCAN (\d+) ([0-9a-f]{256})$', result.stdout, re.M)
assert len(native) == len(cases)
expected_counts = [1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 0, 0xFFFFFFFF, 0, 2, 1, 1, 1, 4, 3]
assert list(map(lambda row: int(row[0]), native)) == expected_counts
float_outputs = [[struct.pack('>f', 1.5)], [struct.pack('>d', -2.75)], [struct.pack('>f', 0.001)],
    [struct.pack('>f', value) for value in (0.0, 90.618, 175.818, 90.382)],
    [struct.pack('>I', 0), struct.pack('>I', 0), struct.pack('>f', 1.2)]]
for (_, memory), values in zip(native[15:], float_outputs):
    expected = bytearray(b'\xcd' * 128)
    for index, value in enumerate(values):
        expected[index * 16:index * 16 + len(value)] = value
    assert bytes.fromhex(memory) == expected
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
records = []
for (value, fmt), (count, memory) in zip(cases, native):
    uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
    uc.mem_map(0x80000000, 24 * 1024 * 1024)
    uc.mem_map(0x90000000, 64 * 1024 * 1024)
    for i in range(18):
        if layout[36 + i]:
            uc.mem_write(layout[18 + i], dol[layout[i]:layout[i] + layout[36 + i]])
    uc.mem_write(0x80600000, value + b'\0')
    uc.mem_write(0x80600200, fmt + b'\0')
    uc.mem_write(0x80600400, b'\xcd' * 256)
    for i, val in {1: 0x80700000, 2: 0x805335E0, 3: 0x80600000, 4: 0x80600200, 13: 0x8052E720,
        **{i: 0x80600400 + (i - 5) * 16 for i in range(5, 11)}}.items():
        uc.reg_write(getattr(ppc, f'UC_PPC_REG_{i}'), val)
    uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F0000)
    uc.reg_write(ppc.UC_PPC_REG_CR, 0)
    uc.reg_write(ppc.UC_PPC_REG_MSR, 0)
    uc.reg_write(ppc.UC_PPC_REG_0, 0x2000)
    uc.mem_write(0x807E0000, struct.pack('>I', 0x7C000124))
    uc.emu_start(0x807E0000, 0x807E0004, count=1)
    uc.reg_write(ppc.UC_PPC_REG_0, 0)
    try:
        uc.emu_start(0x8019D434, 0x807F0000, count=1000000)
    except Exception as error:
        pc = uc.reg_read(ppc.UC_PPC_REG_PC)
        print('Original PPC oracle exception:', value, fmt, hex(pc), bytes(uc.mem_read(pc, 4)).hex())
        if b'%f' not in fmt and b'%lf' not in fmt:
            raise
        assert bytes(uc.mem_read(pc - 4, 4)) == bytes.fromhex('f3e10178')
        records.append({'input': value.hex(), 'format': fmt.hex(), 'nativeCount': int(count),
            'originalOracleUnavailable': str(error), 'precedingPairedInstruction': '801983B8:F3E10178',
            'nativeLogicalFixturePassed': True, 'passed': None})
        continue
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x807F0000
    assert uc.reg_read(ppc.UC_PPC_REG_1) == 0x80700000
    expected_count = uc.reg_read(ppc.UC_PPC_REG_3)
    expected = bytes(uc.mem_read(0x80600400, 128))
    records.append({'input': value.hex(), 'format': fmt.hex(), 'nativeCount': int(count),
        'originalCount': expected_count, 'outputEqual': bytes.fromhex(memory) == expected,
        'passed': int(count) == expected_count and bytes.fromhex(memory) == expected})
verified = [row for row in records if row['passed'] is not None]
assert len(verified) == 15 and all(row['passed'] for row in verified)
report = {'result': 'RESTORED_SCAN_INTEGER_PPC_PASS_FLOAT_ORACLE_UNAVAILABLE',
    'cases': records, 'dolSha256': sha(dol_path), 'probeBuildSha256': sha(output / 'probe-build.json'),
    'continuationRoutes': args.continuation_routes,
    'scriptSha256': sha(Path(__file__)), 'nativeLogSha256': sha(output / 'original-compare-native.log'),
    'limits': ['Original PPC software oracle on own DOL with flat RAM/sentinel/FP-enabled MSR2000 fixture (translation disabled); not physical Wii timing/IRQ.',
        'Integer/string/literal/malformed/EOF scanning return+128output/canary bytes and stack restoration, not all volatile CPU state.',
        'Existing native dispatcher/interpreter used; pure all-static execution and all float/NaN/rounding domains not accepted by these cases.']}
(output / 'original-compare.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], len(verified), 'original-PPC matches;', len(records) - len(verified), 'native logical float fixtures only')
