"""Original primary callback and guarded existing-InputManager transition adapter; no live binding."""
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
output = root / 'input-connection-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
source = Path('experiments/wii-static-recomp/stock_input_connection_probe.cpp').resolve()
adapter = Path('experiments/wii-static-recomp/stock_input_connection_bridge.h').resolve()
obj, exe = output / 'probe.cpp.o', output / 'input-connection-probe'
cases = list(itertools.product(range(8), range(2), [0, 0xFFFFFFFF]))
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
    assert result.returncode == 0 and result.stdout.count('CALLBACK ') == len(cases), result.returncode
    assert 'PRIMARY_CONNECTION_ADAPTER_PASS 7 polls/4 registration-context refusals' in result.stdout
    (output / 'native.json').write_text(json.dumps({'result': 'NATIVE_CONNECTION_ADAPTER_COMPLETE', 'count': len(cases),
        'baseBuildSha256': sha(build_path), 'sourceSha256': sha(source), 'adapterSha256': sha(adapter), 'objectSha256': sha(obj),
        'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'), 'recipeSha256': sha(Path(__file__)),
        'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
            and Path(arg).suffix in ('.o', '.a') and arg != str(obj)}}, indent=2) + '\n')
    print('NATIVE_CONNECTION_ADAPTER_COMPLETE', len(cases), 'callback/7 transition polls/4 refusals')
    sys.exit(0)
assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc
native_path = output / 'native.json'
native = json.loads(native_path.read_text())
for path, key in [(Path(__file__), 'recipeSha256'), (source, 'sourceSha256'), (adapter, 'adapterSha256'),
        (obj, 'objectSha256'), (exe, 'executableSha256'), (output / 'probe.log', 'logSha256')]:
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
fragments = [(0x80009CF8, 0xBC), (0x80006284, 0x30), (0x800061D0, 0xB4), (0x800378D0, 8)]
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for address, size in fragments:
    uc.mem_write(address, read(address, size))
lines = [line for line in (output / 'probe.log').read_text().splitlines() if line.startswith('CALLBACK ')]
assert len(lines) == len(cases)
results = []
for index, ((pattern, previous, result), line) in enumerate(zip(cases, lines)):
    initial = bytearray((i * 37 + pattern) & 255 for i in range(0xB30))
    initial[0] = previous
    uc.mem_write(0x804579C0 - 16, b'\xCD' * 16 + initial + b'\xCD' * 16)
    uc.mem_write(0x80526B10, struct.pack('>I', 0xCAFEBABE))
    for register, value in [(ppc.UC_PPC_REG_1, 0x80700000), (ppc.UC_PPC_REG_13, 0x8052E720),
            (ppc.UC_PPC_REG_3, 0), (ppc.UC_PPC_REG_4, result), (ppc.UC_PPC_REG_29, 0x11111111),
            (ppc.UC_PPC_REG_30, 0x22222222), (ppc.UC_PPC_REG_31, 0x33333333), (ppc.UC_PPC_REG_LR, 0x8009BB80)]:
        uc.reg_write(register, value)
    uc.emu_start(0x80009CF8, 0x8009BB80, count=4096)
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == uc.reg_read(ppc.UC_PPC_REG_LR) == 0x8009BB80
    assert uc.reg_read(ppc.UC_PPC_REG_1) == 0x80700000
    assert [uc.reg_read(getattr(ppc, f'UC_PPC_REG_{i}')) for i in [29, 30, 31]] == [0x11111111, 0x22222222, 0x33333333]
    actual = bytes(uc.mem_read(0x804579C0, 0xB30))
    expected = bytearray(0xB30)
    expected[0] = 1 if result == 0 else 0
    assert actual == expected
    selected = struct.unpack('>I', bytes(uc.mem_read(0x80526B10, 4)))[0]
    assert selected == (0 if result == 0 else 0xCAFEBABE)
    _, native_index, native_selected, native_hex = line.split()
    assert int(native_index) == index and int(native_selected) == selected and actual == bytes.fromhex(native_hex)
    assert bytes(uc.mem_read(0x804579C0 - 16, 16)) == bytes(uc.mem_read(0x804584F0, 16)) == b'\xCD' * 16
    results.append({'id': index, 'pattern': pattern, 'previous': previous, 'result': result,
        'allRecordBytesExact': True, 'selectedChannel': selected})
(output / 'original-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_NATIVE_PRIMARY_CALLBACK_PASS',
    'count': len(cases), 'results': results, 'dolSha256': sha(dol_path), 'recipeSha256': sha(Path(__file__)),
    'nativeReportSha256': sha(native_path), 'fragments': {f'{a:08X}': hashlib.sha256(read(a, n)).hexdigest() for a, n in fragments},
    'limits': ['Full original channel0 success/disconnect callback including original memset; software750CL, not physical hardware.',
        'Adapter transition tests use controlled IInputSource through the actual InputManager; no physical inputs or game binding.',
        'Only known registered original callback accepted; other channels/callbacks, SDK lifecycle and sample forwarding pending.']}, indent=2) + '\n')
print('ORIGINAL_NATIVE_PRIMARY_CALLBACK_PASS', len(cases), 'adapter7 polls/4 refusals')
