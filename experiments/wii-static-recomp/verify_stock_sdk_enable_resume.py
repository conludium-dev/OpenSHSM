"""Compare the native exact SDK continuation with owned DOL instructions, not a full IRQ oracle."""
from pathlib import Path
import hashlib
import json
import platform
import struct
import sys

assert platform.machine() == 'x86_64', 'Use the existing isolated x64 Unicorn setup'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-sdk-enable-resume'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
address = 0x80217500
section = next(i for i in range(18) if header[18 + i] <= address
    and address + 20 <= header[18 + i] + header[36 + i])
offset = header[section] + address - header[18 + section]
body = dol[offset:offset + 20]
assert struct.unpack('>5I', body) == (0x7C6000A6, 0x60648000, 0x7C800124, 0x54638FFE, 0x4E800020)
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
native_log = output / 'fixed.log'
assert sha(native_log) == build['records']['fixed']['logSha256']
assert sha(output / 'fixed-probe') == build['records']['fixed']['executableSha256']
rows = [list(map(int, line.split()[1:])) for line in native_log.read_text().splitlines()
    if line.startswith('RESUME ')]
assert len(rows) == 7 and len({row[0] for row in rows}) == 7
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
uc.mem_write(address, body)
cases = []
for value, native_r3, native_pc in rows:
    before = [0x12340000 + i * 256 for i in range(32)]
    before[3] = value
    for i, register in enumerate(before):
        uc.reg_write(getattr(ppc, 'UC_PPC_REG_' + str(i)), register)
    uc.reg_write(ppc.UC_PPC_REG_LR, 0x8009BB80)
    uc.emu_start(0x8021750C, 0x8009BB80, count=2)
    actual = [uc.reg_read(getattr(ppc, 'UC_PPC_REG_' + str(i))) for i in range(32)]
    pc = uc.reg_read(ppc.UC_PPC_REG_PC)
    expected = list(before)
    expected[3] = native_r3
    assert actual == expected and pc == native_pc == 0x8009BB80
    cases.append({'inputR3': value, 'originalR3': actual[3], 'nativeR3': native_r3,
        'originalPc': pc, 'nativePc': native_pc, 'otherGprPreserved': True})
report = {'result': 'ORIGINAL_SDK_CONTINUATION_NATIVE_COMPARISON_PASS', 'cases': cases,
    'dolSha256': sha(dol_path), 'bodySha256': hashlib.sha256(body).hexdigest(),
    'buildSha256': sha(build_path), 'nativeLogSha256': sha(native_log),
    'recipeSha256': sha(Path(__file__)),
    'limits': ['Only original two-instruction continuation8021750C..80217510 under software750CL.',
        'No execution of mfmsr/mtmsr, pending IRQ scheduling, whole callback or physical Wii oracle.',
        'A passing continuation does not establish the cause of the live movie stall.']}
(output / 'original-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], len(cases))
