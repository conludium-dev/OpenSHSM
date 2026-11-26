"""Verify original DSP IRQ tail restores its passed context, independently of current-thread identity."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import struct
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--oracle', action='store_true')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'sdk-irq-tail'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if not args.oracle:
    build_path = root / 'window-cache-filtered/build.json'
    build = json.loads(build_path.read_text())
    command = list(build['linkCommand'])
    command[command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
    source = Path('experiments/wii-static-recomp/stock_sdk_irq_tail_probe.cpp').resolve()
    full = json.loads((root / 'window-quantization/build.json').read_text())
    arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'main_output.cpp')
    obj = output / 'probe.cpp.o'
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
    (output / 'compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    command.insert(1, str(obj))
    exe = output / 'sdk-irq-tail-probe'
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    (output / 'probe.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and result.stdout.count('TAIL ') == 12, result.stdout + result.stderr
    (output / 'native.json').write_text(json.dumps({'result': 'NATIVE_SDK_IRQ_TAIL_FIXTURES_COMPLETE',
        'baseBuildSha256': sha(build_path), 'sourceSha256': sha(source), 'executableSha256': sha(exe),
        'objectSha256': sha(obj), 'logSha256': sha(output / 'probe.log'), 'recipeSha256': sha(Path(__file__)),
        'linkCommand': command}, indent=2) + '\n')
    print('NATIVE_SDK_IRQ_TAIL_FIXTURES_COMPLETE 12')
    sys.exit(0)

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc
native_path = output / 'native.json'
native = json.loads(native_path.read_text())
assert native['recipeSha256'] == sha(Path(__file__)) and native['logSha256'] == sha(output / 'probe.log')
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
def read(address, size):
    section = next(i for i in range(18) if header[18 + i] <= address
        and address + size <= header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    return dol[offset:offset + size]
assert read(0x8022CD5C, 4) == struct.pack('>I', 0x7C9F2378)
assert read(0x80213834, 4) == struct.pack('>I', 0x906400D4)
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for address, size in [(0x8022CDCC, 28), (0x80213830, 92)]:
    uc.mem_write(address, read(address, size))
cases = []
for line in (output / 'probe.log').read_text().splitlines():
    if not line.startswith('TAIL '):
        continue
    target, thread, owner, *expected = map(int, line.split()[1:])
    for address, value in [(0x800000D4, 0x80541000), (0x800000E4, thread), (0x800000D8, owner),
        (target + 0x19C, 0xB032), (0x80550000 + 740, 0xFFFFFFFC), (0x80550000 + 732, 0xAABBCCDD)]:
        uc.mem_write(address, struct.pack('>I', value))
    uc.reg_write(ppc.UC_PPC_REG_1, 0x80550000)
    uc.reg_write(ppc.UC_PPC_REG_31, target)
    uc.reg_write(ppc.UC_PPC_REG_MSR, 0)
    uc.emu_start(0x8022CDCC, 0xFFFFFFFC, count=128)
    actual = [struct.unpack('>I', uc.mem_read(a, 4))[0] for a in [0x800000D4, 0x800000E4]]
    actual += [uc.reg_read(reg) for reg in [ppc.UC_PPC_REG_PC, ppc.UC_PPC_REG_1, ppc.UC_PPC_REG_LR, ppc.UC_PPC_REG_31]]
    assert actual == expected, (target, thread, owner, actual, expected)
    cases.append({'passedContext': f'{target:08X}', 'currentThread': f'{thread:08X}',
        'fpOwner': f'{owner:08X}', 'original': actual, 'native': expected})
assert len(cases) == 12
(output / 'original-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_NATIVE_SDK_IRQ_TAIL_COMPARISON_PASS',
    'cases': cases, 'dolSha256': sha(dol_path), 'nativeReportSha256': sha(native_path), 'recipeSha256': sha(Path(__file__)),
    'fragments': {f'{a:08X}': hashlib.sha256(read(a, size)).hexdigest()
        for a, size in [(0x8022CDCC, 28), (0x80213830, 92)]},
    'limits': ['Original DSP IRQ epilogue and context setter only; supplied saved stack/R31, no MMIO handler body.',
        'Full scheduler/thread transfer and physical Wii nested IRQ behavior not executed.',
        'SDK restores supplied context in D4; E4 identity alone does not select the return context.']}, indent=2) + '\n')
print('ORIGINAL_NATIVE_SDK_IRQ_TAIL_COMPARISON_PASS 12')
