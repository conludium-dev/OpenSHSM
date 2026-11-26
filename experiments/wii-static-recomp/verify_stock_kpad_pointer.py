"""Original invalid-pointer function and initial projection tail versus retained native code."""
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
output = root / 'kpad-pointer-research'
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
constants = read(0x8052EDB0, 8)
assert struct.unpack('>ff', constants) == (0.0, 0.5)
cases = []
for old in [0, 1, 2, 0xFF, 0xFE]:
    data = bytearray((i * 37 + old) & 255 for i in range(0x600))
    data[0x5E] = old
    cases.append((0, 0, bytes(data)))
for validity, point, basis, scale in itertools.product([1, 2, 0xFF, 0xFE],
        [(-0.75, -0.25), (0.0, 0.0), (0.25, 0.75), (1.25, -1.5)],
        [(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.6, 0.8)], [0.5, 1.0, 2.0]):
    data = bytearray(0x600)
    for offset, value in [(0xD4, basis[0]), (0xD8, basis[1]), (0xDC, basis[0]), (0xE0, basis[1]),
            (0x4C8, 1.0), (0x4CC, 0.0), (0x120, point[0]), (0x124, point[1]),
            (0x12C, point[0] + 0.125), (0x130, point[1] - 0.125),
            (0xE4, 0.125), (0xE8, -0.25), (0xEC, scale)]:
        struct.pack_into('>f', data, offset, value)
    struct.pack_into('>5I', data, 0x20, *([0xDEADBEEF] * 5))
    cases.append((1, validity, bytes(data)))
assert len(cases) == 197
case_bytes = constants + b''.join(bytes([kind, valid]) + data for kind, valid, data in cases)
if not args.oracle:
    input_path = output / 'cases.bin'
    input_path.write_bytes(case_bytes)
    build_path = root / 'window-legacy-context/build.json'
    command = list(json.loads(build_path.read_text())['linkCommand'])
    full = root / 'window-quantization'
    command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
    arguments = next(row['arguments'] for row in json.loads((full / 'build.json').read_text())['compiled']
        if row['source'] == 'main_output.cpp')
    source = Path('experiments/wii-static-recomp/stock_kpad_pointer_probe.cpp').resolve()
    obj = output / 'probe.cpp.o'
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=60)
    (output / 'compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    command.insert(1, str(obj))
    exe = output / 'kpad-pointer-probe'
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    result = subprocess.run([str(exe), str(input_path)], capture_output=True, text=True, timeout=20)
    (output / 'probe.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and result.stdout.count('POINTER ') == len(cases), result.returncode
    (output / 'native.json').write_text(json.dumps({'result': 'NATIVE_POINTER_PATHS_COMPLETE', 'count': len(cases),
        'baseBuildSha256': sha(build_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'), 'inputSha256': sha(input_path),
        'recipeSha256': sha(Path(__file__)), 'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command
            if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a') and arg != str(obj)}}, indent=2) + '\n')
    print('NATIVE_POINTER_PATHS_COMPLETE', len(cases))
    sys.exit(0)
assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc
native_path = output / 'native.json'
native = json.loads(native_path.read_text())
assert native['recipeSha256'] == sha(Path(__file__))
assert sha(Path('experiments/wii-static-recomp/stock_kpad_pointer_probe.cpp')) == native['sourceSha256']
assert sha(output / 'probe.cpp.o') == native['objectSha256']
assert sha(output / 'probe.log') == native['logSha256']
assert sha(output / 'kpad-pointer-probe') == native['executableSha256']
assert (output / 'cases.bin').read_bytes() == case_bytes
for path, expected in native['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
uc.mem_write(0x80279440, read(0x80279440, 0x5CC))
uc.mem_write(0x8052EDB0, constants)
uc.mem_write(0x8052B070, b'\0' * 8)
lines = [line for line in (output / 'probe.log').read_text().splitlines() if line.startswith('POINTER ')]
assert len(lines) == len(cases)
results = []
for index, ((kind, validity, data), line) in enumerate(zip(cases, lines)):
    block = 0x80540000
    uc.mem_write(block - 16, b'\xCD' * 16 + data + b'\xCD' * 16)
    for offset, value in [(0x18, 0x12345678), (0x1C, 0x23456789), (0x24, 0x8009BB80)]:
        uc.mem_write(0x80700000 + offset, struct.pack('>I', value))
    for register, value in [(ppc.UC_PPC_REG_1, 0x80700020 if kind == 0 else 0x80700000),
            (ppc.UC_PPC_REG_2, 0x805335E0), (ppc.UC_PPC_REG_13, 0x8052E720),
            (ppc.UC_PPC_REG_3, block), (ppc.UC_PPC_REG_4, 0), (ppc.UC_PPC_REG_30, block),
            (ppc.UC_PPC_REG_31, validity), (ppc.UC_PPC_REG_LR, 0x8009BB80),
            (ppc.UC_PPC_REG_MSR, 0x2000)]:
        uc.reg_write(register, value)
    uc.emu_start(0x80279440 if kind == 0 else 0x802797BC, 0x8009BB80, count=256)
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x8009BB80
    assert uc.reg_read(ppc.UC_PPC_REG_1) == 0x80700020
    assert uc.reg_read(ppc.UC_PPC_REG_LR) == 0x8009BB80
    actual = bytes(uc.mem_read(block, 0x600))
    _, native_index, native_hex = line.split()
    assert int(native_index) == index and actual == bytes.fromhex(native_hex), (index, kind)
    if kind == 0:
        expected = bytearray(data)
        expected[0x5E] = 0
        assert actual == expected
    else:
        assert actual[0x5E] == validity
        assert actual[0x28:0x34] == b'\0' * 12
    assert bytes(uc.mem_read(block - 16, 16)) == bytes(uc.mem_read(block + 0x600, 16)) == b'\xCD' * 16
    results.append({'id': index, 'path': 'invalid' if kind == 0 else 'initial-projection-tail',
        'positionBits': [f'{word:08X}' for word in struct.unpack_from('>II', actual, 0x20)],
        'validity': actual[0x5E], 'exactContextBytes': True})
(output / 'original-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_NATIVE_POINTER_PATHS_PASS',
    'count': len(cases), 'results': results, 'dolSha256': sha(dol_path), 'nativeReportSha256': sha(native_path),
    'recipeSha256': sha(Path(__file__)), 'functionSha256': hashlib.sha256(read(0x80279440, 0x5CC)).hexdigest(),
    'originalStartupSha256': hashlib.sha256(read(0x800064FC, 16)).hexdigest(),
    'constantWords': [f'{word:08X}' for word in struct.unpack('>II', constants)],
    'fieldEvidence': {'position': ['8027988C', '80279894'], 'velocity': ['802798A0', '802798A4'],
        'speed': ['802798A8'], 'validityClear': ['80279468'], 'validityStore': ['802799F0']},
    'limits': ['Five complete invalid-pointer calls; 192 resumed initial-projection tails with supplied basis/calibration/stack/global zero vector.',
        'No skipped original instructions on tested paths; software750CL, not physical Wii capture.',
        'Smoothing, raw IR reconstruction, calibration producers, normalized range, full KPADRead and host input bridge remain unverified.']}, indent=2) + '\n')
print('ORIGINAL_NATIVE_POINTER_PATHS_PASS', len(cases))
