"""Compare actual native SDK cache loop with unmodified owned PPC instructions in software750CL."""
from pathlib import Path
import argparse
import hashlib
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
output = root / 'cache-invalidate-fixtures'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if not args.oracle:
    base = root / 'window-context-observe'
    build_path = base / 'build.json'
    build = json.loads(build_path.read_text())
    assert sha(base / 'OpenSHSMStockContextObserver') == build['executableSha256']
    command = list(build['linkCommand'])
    command[command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
    source = Path('experiments/wii-static-recomp/stock_cache_invalidate_probe.cpp').resolve()
    full = json.loads((root / 'window-quantization/build.json').read_text())
    arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'main_output.cpp')
    obj = output / 'probe.cpp.o'
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
    (output / 'compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    command.insert(1, str(obj))
    exe = output / 'cache-invalidate-probe'
    command[command.index('-o') + 1] = str(exe)
    result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
    (output / 'link.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    (output / 'probe.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and result.stdout.count('CACHE ') == 68, result.stdout + result.stderr
    (output / 'native.json').write_text(json.dumps({'result': 'NATIVE_CACHE_LOOP_FIXTURES_COMPLETE',
        'baseBuildSha256': sha(build_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'), 'linkCommand': command,
        'recipeSha256': sha(Path(__file__)), 'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command
            if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a') and arg != str(obj)},
        'limits': ['Actual generated function and linked runtime, IRQ delivery suppressed by supplied in_callback=true/EEoff.',
            'Native loop return alone is not original Wii or live IRQ/cache coherence correctness.']}, indent=2) + '\n')
    print('NATIVE_CACHE_LOOP_FIXTURES_COMPLETE 68; original comparison pending')
    sys.exit(0)

assert platform.machine() == 'x86_64', 'Use the existing isolated x64 Unicorn setup'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc
native_path = output / 'native.json'
native = json.loads(native_path.read_text())
assert native['recipeSha256'] == sha(Path(__file__))
assert sha(output / 'probe.log') == native['logSha256']
assert sha(output / 'cache-invalidate-probe') == native['executableSha256']
assert sha(output / 'probe.cpp.o') == native['objectSha256']
assert sha(Path('experiments/wii-static-recomp/stock_cache_invalidate_probe.cpp')) == native['sourceSha256']
for path, expected in native['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
address = 0x80212FA0
section = next(i for i in range(18) if header[18 + i] <= address
    and address + 44 <= header[18 + i] + header[36 + i])
offset = header[section] + address - header[18 + section]
body = dol[offset:offset + 44]
assert struct.unpack_from('>I', body, 0x1C)[0] == 0x7C001BAC
guest_source = next(Path(arg).with_suffix('') for arg in native['linkCommand']
    if Path(arg).name == 'output_38.cpp.o')
text = guest_source.read_text()
start = text.index('void func_80212FA0(CPUContext& ctx) {')
end = text.index('\nvoid func_', start + 1)
facts = [(int(a, 16), int(b, 16)) for a, b in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', text[start:end])]
assert len(facts) == 11
assert facts == [(address + i * 4, value) for i, value in enumerate(struct.unpack('>11I', body))]
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
uc.mem_write(address, body)
cases = []
for line in (output / 'probe.log').read_text().splitlines():
    if not line.startswith('CACHE '):
        continue
    entry, start, size, ctr, *expected = map(int, line.split()[1:])
    before = [0x12340000 + i * 256 for i in range(32)]
    before[3:6] = [start, size, 0xCAFEBABE]
    for i, value in enumerate(before):
        uc.reg_write(getattr(ppc, 'UC_PPC_REG_' + str(i)), value)
    uc.reg_write(ppc.UC_PPC_REG_CR, 0xAAAAAAAA)
    uc.reg_write(ppc.UC_PPC_REG_CTR, ctr)
    uc.reg_write(ppc.UC_PPC_REG_LR, 0x8009BB9C)
    uc.emu_start(entry, 0x8009BB9C, count=256)
    gpr = [uc.reg_read(getattr(ppc, 'UC_PPC_REG_' + str(i))) for i in range(32)]
    actual = gpr[3:6] + [uc.reg_read(ppc.UC_PPC_REG_CTR), uc.reg_read(ppc.UC_PPC_REG_CR), uc.reg_read(ppc.UC_PPC_REG_PC)]
    assert actual == expected, (entry, start, size, ctr, actual, expected)
    assert all(gpr[i] == before[i] for i in range(32) if i < 3 or i > 5)
    cases.append({'entry': f'{entry:08X}', 'address': start, 'size': size, 'inputCtr': ctr,
        'original': actual, 'native': expected})
assert len(cases) == 68
(output / 'original-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_NATIVE_CACHE_LOOP_COMPARISON_PASS',
    'cases': cases, 'dolSha256': sha(dol_path), 'fragmentSha256': hashlib.sha256(body).hexdigest(),
    'nativeReportSha256': sha(native_path), 'recipeSha256': sha(Path(__file__)),
    'compiledGuestSourcePath': str(guest_source), 'compiledGuestSourceSha256': sha(guest_source),
    'originalInstructionFacts': [{'address': f'{a:08X}', 'opcode': f'{b:08X}'} for a, b in facts],
    'limits': ['Unmodified original44byte integer/cache loop under software750CL; no skipped/replaced instructions.',
        'Native interrupt delivery suppressed; four continuation cases are supplied resumed registers, not real IRQ traces.',
        'Cache coherence/device effects and physical Wii timing unverified; not full SHSM gameplay/milestone acceptance.']}, indent=2) + '\n')
print('ORIGINAL_NATIVE_CACHE_LOOP_COMPARISON_PASS', len(cases))
