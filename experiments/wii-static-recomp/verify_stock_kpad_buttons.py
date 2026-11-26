"""Full original button/repeat helper versus actual native functions; no input bridge or hardware claim."""
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
output = root / 'kpad-buttons-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
cases = []
for t, flag, old, raw, extra, ext in itertools.product([0, 1, 2, 16, 17], [0, 1],
        [0, 0x800, 0xFFFF, 0x10000], [0, 0x800, 0xFFFFFFFF], [0, 0x6000], [0, 1]):
    cases.append([t, flag, old, raw, extra, ext, 1, 1, 0, 5, 5, 2, 0, 5])
for t, old, timer_state in itertools.product([0, 1, 2, 16, 17], [0, 0x800, 0x80000000],
        [(1, 4, 5, 5, 2), (1, 3, 5, 5, 2), (1, 4, 5, 5, 0), (1, 19999, 20000, 5, 2),
         (1, 39999, 5, 5, 2), (65535, 65535, 1, 5, 2), (20, 1, 10, 10, 3)]):
    step, timer, next_tick, delay, interval = timer_state
    cases.append([t, 0, old, 0x800, 0x6000, 1, 1, step, timer, next_tick, delay, interval, timer, next_tick])
assert len(cases) == 585
if not args.oracle:
    input_path = output / 'cases.txt'
    input_path.write_text('\n'.join(' '.join(map(str, row)) for row in cases) + '\n')
    build_path = root / 'window-legacy-context/build.json'
    build = json.loads(build_path.read_text())
    command = list(build['linkCommand'])
    full = root / 'window-quantization'
    command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
    arguments = next(row['arguments'] for row in json.loads((full / 'build.json').read_text())['compiled']
        if row['source'] == 'main_output.cpp')
    source = Path('experiments/wii-static-recomp/stock_kpad_buttons_probe.cpp').resolve()
    obj = output / 'probe.cpp.o'
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=60)
    (output / 'compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    command.insert(1, str(obj))
    exe = output / 'kpad-buttons-probe'
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    result = subprocess.run([str(exe), str(input_path)], capture_output=True, text=True, timeout=20)
    (output / 'probe.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and result.stdout.count('BUTTONS ') == len(cases)
    (output / 'native.json').write_text(json.dumps({'result': 'NATIVE_KPAD_BUTTON_REPEAT_COMPLETE',
        'cases': cases, 'baseBuildSha256': sha(build_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'), 'inputSha256': sha(input_path),
        'recipeSha256': sha(Path(__file__)), 'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command
            if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a') and arg != str(obj)}}, indent=2) + '\n')
    print('NATIVE_KPAD_BUTTON_REPEAT_COMPLETE', len(cases))
    sys.exit(0)
assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc
native_path = output / 'native.json'
native = json.loads(native_path.read_text())
assert native['recipeSha256'] == sha(Path(__file__)) and native['cases'] == cases
assert sha(output / 'probe.log') == native['logSha256']
assert sha(output / 'kpad-buttons-probe') == native['executableSha256']
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
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
fragments = [(0x80278450, 160), (0x802782B0, 416)]
for address, size in fragments:
    uc.mem_write(address, read(address, size))
lines = [line for line in (output / 'probe.log').read_text().splitlines() if line.startswith('BUTTONS ')]
assert len(lines) == len(cases)
results = []
for index, (values, line) in enumerate(zip(cases, lines)):
    t, flag, old, raw, extra, ext, old_ext, step, timer, next_tick, delay, interval, ext_timer, ext_next = values
    block = 0x80540000
    initial = bytearray(0x600)
    struct.pack_into('>I', initial, 0, old)
    struct.pack_into('>I', initial, 0x60, old_ext)
    struct.pack_into('>6H', initial, 0x500, timer, next_tick, delay, interval, ext_timer, ext_next)
    initial[0x555] = flag
    uc.mem_write(block - 16, b'\xCD' * 16 + initial + b'\xCD' * 16)
    for register, value in [(ppc.UC_PPC_REG_3, block), (ppc.UC_PPC_REG_4, t), (ppc.UC_PPC_REG_5, step),
        (ppc.UC_PPC_REG_6, raw), (ppc.UC_PPC_REG_7, extra), (ppc.UC_PPC_REG_8, ext), (ppc.UC_PPC_REG_LR, 0x8009BB80)]:
        uc.reg_write(register, value)
    uc.emu_start(0x80278450, 0x8009BB80, count=256)
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x8009BB80
    _, native_index, native_hex = line.split()
    actual = bytes(uc.mem_read(block, 0x600))
    assert int(native_index) == index and actual == bytes.fromhex(native_hex), (index, values)
    assert bytes(uc.mem_read(block - 16, 16)) == bytes(uc.mem_read(block + 0x600, 16)) == b'\xCD' * 16
    results.append({'id': index, 'heldTriggerRelease': struct.unpack_from('>III', actual),
        'extensionWords': struct.unpack_from('>III', actual, 0x60),
        'timers': struct.unpack_from('>6H', actual, 0x500), 'exactContextBytes': True})
(output / 'original-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_NATIVE_KPAD_BUTTON_REPEAT_PASS',
    'cases': cases, 'results': results, 'dolSha256': sha(dol_path), 'nativeReportSha256': sha(native_path),
    'recipeSha256': sha(Path(__file__)), 'fragments': {f'{a:08X}': hashlib.sha256(read(a, size)).hexdigest() for a, size in fragments},
    'limits': ['Full integer button helper and repeat tail under software750CL versus actual linked native functions; no skipped instructions.',
        'Controlled prior words/reset/timer/samplecount states; raw-device sampling/calibration/lifecycle and physical Wii timing unverified.',
        'Input bridge not installed; IR/extension axes/whole KPAD read and hardware-controller acceptance still pending.']}, indent=2) + '\n')
print('ORIGINAL_NATIVE_KPAD_BUTTON_REPEAT_PASS', len(cases))
