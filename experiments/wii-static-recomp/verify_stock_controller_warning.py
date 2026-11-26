"""Original SHSM controller-warning producer versus its actual compiled native function."""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import platform
import re
import struct
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--oracle', action='store_true')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'controller-warning-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
cases = list(itertools.product([0, 1], [0, 1], [0, 1], [0xFFFFFFFF, 0, 1, 16],
    [0, 1, 255], [0, 1, 255], [0, 0x10, 0x20, 0x7F]))
assert len(cases) == 1152
source = Path('experiments/wii-static-recomp/stock_controller_warning_probe.cpp').resolve()
obj = output / 'probe.cpp.o'
exe = output / 'controller-warning-probe'
input_path = output / 'cases.txt'
if not args.oracle:
    input_path.write_text('\n'.join(' '.join(map(str, row)) for row in cases) + '\n')
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
    result = subprocess.run([str(exe), str(input_path)], capture_output=True, text=True, timeout=20)
    (output / 'probe.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and result.stdout.count('WARNING ') == len(cases), result.returncode
    (output / 'native.json').write_text(json.dumps({'result': 'NATIVE_WARNING_PRODUCER_COMPLETE', 'count': len(cases),
        'baseBuildSha256': sha(build_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'), 'inputSha256': sha(input_path),
        'recipeSha256': sha(Path(__file__)), 'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command
            if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a') and arg != str(obj)}}, indent=2) + '\n')
    print('NATIVE_WARNING_PRODUCER_COMPLETE', len(cases))
    sys.exit(0)
assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc
native_path = output / 'native.json'
native = json.loads(native_path.read_text())
for path, key in [(Path(__file__), 'recipeSha256'), (source, 'sourceSha256'), (obj, 'objectSha256'),
        (exe, 'executableSha256'), (output / 'probe.log', 'logSha256'), (input_path, 'inputSha256')]:
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
fragments = [(0x80009F60, 0xC8), (0x80006A20, 8), (0x8018E09C, 8), (0x80202FEC, 28)]
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for address, size in fragments:
    uc.mem_write(address, read(address, size))
lines = [line for line in (output / 'probe.log').read_text().splitlines() if line.startswith('WARNING ')]
assert len(lines) == len(cases)
results = []
for index, (values, line) in enumerate(zip(cases, lines)):
    initialized, paused, connected, count, error, type_value, mask = values
    for address, value in [(0x80529148, initialized), (0x8052A440, paused), (0x804579C0, connected),
            (0x80457A25, error), (0x80457A24, type_value)]:
        uc.mem_write(address, bytes([value]))
    for address, value in [(0x804584CC, count), (0x8052A83C, mask), (0x80529D20, 0x80560000), (0x80561FEC, 0xCAFEBABE)]:
        uc.mem_write(address, struct.pack('>I', value))
    for register, value in [(ppc.UC_PPC_REG_1, 0x80700000), (ppc.UC_PPC_REG_13, 0x8052E720),
            (ppc.UC_PPC_REG_31, 0x12345678), (ppc.UC_PPC_REG_LR, 0x8009BB80)]:
        uc.reg_write(register, value)
    uc.emu_start(0x80009F60, 0x8009BB80, count=256)
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == uc.reg_read(ppc.UC_PPC_REG_LR) == 0x8009BB80
    assert uc.reg_read(ppc.UC_PPC_REG_1) == 0x80700000 and uc.reg_read(ppc.UC_PPC_REG_31) == 0x12345678
    actual = [struct.unpack('>I', bytes(uc.mem_read(a, 4)))[0] for a in [0x8052A83C, 0x80561FEC]]
    expected_mask, expected_state = mask, 0xCAFEBABE
    if initialized and not paused:
        expected_mask = (mask & ~0x10) if connected else (mask | 0x10)
        if connected and count in [1, 16] and error == 0 and type_value != 255:
            expected_mask = (expected_mask & ~0x20) if type_value == 1 else (expected_mask | 0x20)
            expected_state = 0 if type_value == 1 else 1
    assert actual == [expected_mask, expected_state], (index, values, actual)
    assert list(map(int, line.split()[1:])) == [index, *actual]
    results.append({'id': index, 'input': values, 'warningMask': actual[0], 'extensionState': actual[1]})
table_path = Path('work/private-game/phone-tables-r45/wii-english.bin')
table = table_path.read_bytes()
count = struct.unpack_from('<I', table, 4)[0]
record = next(i for i in range(count) if struct.unpack_from('<I', table, 8 + i * 8)[0] == 0xE7382B19)
pool = 8 + count * 8
position = pool + struct.unpack_from('<I', table, 12 + record * 8)[0] * 2
assert table[position:position + 4] == b'\1\0\1\0'
end = position + 4
while table[end:end + 2] != b'\0\0':
    end += 2
key = read(0x80528910, 8).split(b'\0')[0]
key_hash = 5381
for value in key:
    key_hash = (key_hash * 33 + (value & 0xDF)) & 0xFFFFFFFF
assert key_hash == 0xE7382B19
assert read(0x8020317C, 4) == struct.pack('>I', 0x388DA1F0)
(output / 'original-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_NATIVE_WARNING_PRODUCER_PASS',
    'count': len(cases), 'results': results, 'dolSha256': sha(dol_path), 'recipeSha256': sha(Path(__file__)),
    'nativeReportSha256': sha(native_path), 'fragments': {f'{a:08X}': hashlib.sha256(read(a, n)).hexdigest() for a, n in fragments},
    'warningAnchor': {'tableSha256': sha(table_path), 'record': record, 'keyAddress': '80528910', 'key': key.decode(),
        'hash': 'E7382B19', 'originalText': table[position + 4:end].decode('utf-16-le'),
        'selectionFragmentSha256': hashlib.sha256(read(0x80203058, 0x170)).hexdigest()},
    'limits': ['Complete original SHSM integer warning producer with original callees versus retained compiled function; software750CL, not a hardware trace.',
        'Initialization/pause/connected/sample/type fields supplied; no live callback or host bridge installed.',
        'Text selection is source evidence; full GUI rendering/priority/pause transitions not executed in this fixture.']}, indent=2) + '\n')
print('ORIGINAL_NATIVE_WARNING_PRODUCER_PASS', len(cases))
