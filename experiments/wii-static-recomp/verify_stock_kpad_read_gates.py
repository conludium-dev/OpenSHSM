"""Original complete KPAD early-rejection paths versus actual retained compiled reader."""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import platform
import struct
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--oracle', action='store_true')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'kpad-read-gates-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
cases = list(itertools.product(range(3), range(4), range(2), range(2), [0, 1, 16], range(2)))
assert len(cases) == 288
source = Path('experiments/wii-static-recomp/stock_kpad_read_gate_probe.cpp').resolve()
obj = output / 'probe.cpp.o'
exe = output / 'kpad-read-gates-probe'
if not args.oracle:
    build_path = root / 'window-legacy-context/build.json'
    command = list(json.loads(build_path.read_text())['linkCommand'])
    full = root / 'window-quantization'
    command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
    arguments = next(row['arguments'] for row in json.loads((full / 'build.json').read_text())['compiled']
        if row['source'] == 'main_output.cpp')
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=60)
    (output / 'compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    command.insert(1, str(obj))
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    (output / 'probe.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and result.stdout.count('READ_GATE ') == len(cases), result.returncode
    (output / 'native.json').write_text(json.dumps({'result': 'NATIVE_READ_GATES_COMPLETE', 'count': len(cases),
        'baseBuildSha256': sha(build_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'), 'recipeSha256': sha(Path(__file__)),
        'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
            and Path(arg).suffix in ('.o', '.a') and arg != str(obj)}}, indent=2) + '\n')
    print('NATIVE_READ_GATES_COMPLETE', len(cases))
    sys.exit(0)
assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc
native_path = output / 'native.json'
native = json.loads(native_path.read_text())
for path, key in [(Path(__file__), 'recipeSha256'), (source, 'sourceSha256'), (obj, 'objectSha256'),
        (exe, 'executableSha256'), (output / 'probe.log', 'logSha256')]:
    assert sha(path) == native[key]
for path, expected in native['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
def read(address, size):
    section = next(i for i in range(18) if header[18 + i] <= address
        and address + size <= header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    return dol[offset:offset + size]
fragments = [(0x8027AAC0, 0x73C), (0x801A6854, 0x34), (0x801A68A0, 0x34),
    (0x8027F6C0, 4), (0x8028DAF0, 0x3C), (0x802174E0, 20), (0x80217520, 36)]
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for address, size in fragments:
    uc.mem_write(address, read(address, size))
lines = [line for line in (output / 'probe.log').read_text().splitlines() if line.startswith('READ_GATE ')]
assert len(lines) == len(cases)
results = []
for index, ((gate, channel, error_out, extended, count, buffer), line) in enumerate(zip(cases, lines)):
    block = 0x804EFD58 + channel * 0x578
    uc.mem_write(0x8052B06C, bytes([0 if gate == 0 else 1]))
    uc.mem_write(0x804F52A8, bytes([2 if gate == 1 else 3]))
    uc.mem_write(block + 0x4FF, bytes([1 if gate == 2 else 0]))
    uc.mem_write(0x80560000, struct.pack('>I', 0xCAFEBABE))
    uc.mem_write(0x80550000 - 16, b'\xCD' * 0xB20)
    for i in range(20, 32):
        uc.reg_write(getattr(ppc, f'UC_PPC_REG_{i}'), 0x11000000 + i)
    for register, value in [(ppc.UC_PPC_REG_1, 0x80700000), (ppc.UC_PPC_REG_13, 0x8052E720),
            (ppc.UC_PPC_REG_3, channel), (ppc.UC_PPC_REG_4, 0x80550000 if buffer else 0),
            (ppc.UC_PPC_REG_5, count), (ppc.UC_PPC_REG_6, 0x80560000 if error_out else 0),
            (ppc.UC_PPC_REG_7, extended), (ppc.UC_PPC_REG_LR, 0x8009BB80), (ppc.UC_PPC_REG_MSR, 0)]:
        uc.reg_write(register, value)
    uc.emu_start(0x8027AAD0, 0x8009BB80, count=512)
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == uc.reg_read(ppc.UC_PPC_REG_LR) == 0x8009BB80
    assert uc.reg_read(ppc.UC_PPC_REG_1) == 0x80700000
    assert all(uc.reg_read(getattr(ppc, f'UC_PPC_REG_{i}')) == 0x11000000 + i for i in range(20, 32))
    assert bytes(uc.mem_read(0x80550000 - 16, 0xB20)) == b'\xCD' * 0xB20
    actual = [uc.reg_read(ppc.UC_PPC_REG_3), struct.unpack('>I', bytes(uc.mem_read(0x80560000, 4)))[0],
        uc.mem_read(block + 0x4FF, 1)[0]]
    assert actual == [0, ((-5, -3, -4)[gate] & 0xFFFFFFFF) if error_out else 0xCAFEBABE, 1 if gate == 2 else 0]
    assert list(map(int, line.split()[1:])) == [index, *actual]
    results.append({'id': index, 'gate': gate, 'channel': channel, 'errorOutput': error_out,
        'extended': extended, 'requested': count, 'bufferPresent': buffer, 'actual': actual})
(output / 'original-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_NATIVE_READ_GATES_PASS',
    'count': len(cases), 'results': results, 'dolSha256': sha(dol_path), 'recipeSha256': sha(Path(__file__)),
    'nativeReportSha256': sha(native_path), 'fragments': {f'{a:08X}': hashlib.sha256(read(a, n)).hexdigest() for a, n in fragments},
    'limits': ['Complete reader return paths for three early gates under software750CL; no skipped instructions or supplied host callbacks.',
        'Gate flags/SDK status supplied, not their initialization producers; valid channels0..3 only.',
        'Disconnected-channel reset/callbacks, successful sampling, live lifecycle and original warning predicate remain unverified.']}, indent=2) + '\n')
print('ORIGINAL_NATIVE_READ_GATES_PASS', len(cases))
