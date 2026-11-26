"""Reproduce reached fallback carry omissions against owned DOL single-step execution."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import re
import struct
import subprocess
import sys
import argparse
import shutil
from stock_interpreter_carry import adapt
from stock_interpreter_addze import adapt as adapt_addze

parser = argparse.ArgumentParser()
parser.add_argument('--corrected', action='store_true')
parser.add_argument('--addze', action='store_true')
args = parser.parse_args()

assert platform.machine() == 'x86_64', 'Use isolated x64 Unicorn under Rosetta'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-numeric-flight'
output = root / ('interpreter-carry-corrected' if args.corrected else 'interpreter-carry-repro')
if args.addze:
    output = root / ('interpreter-addze-corrected' if args.corrected else 'interpreter-addze-repro')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
source = Path('experiments/wii-static-recomp/stock_interpreter_carry_probe.cpp').resolve()
obj, exe = output / 'probe.cpp.o', output / 'probe'
command = list(build['linkCommand'])
for arg in command:
    if arg in build['retainedInputs']:
        assert sha(Path(arg)) == build['retainedInputs'][arg]
runtime = None
if args.addze and not args.corrected:
    old_archive = next(arg for arg in command if Path(arg).name == 'libnwiiruntime.a')
    prior = root / 'interpreter-carry-corrected/libnwiiruntime.a'
    prior_build = json.loads((prior.parent / 'build.json').read_text())
    assert sha(prior) == prior_build['runtime']['archiveSha256']
    command[command.index(old_archive)] = str(prior)
if args.corrected:
    original = root / 'window-scan-consume/interpreter.cpp'
    source_runtime, object_runtime = output / 'interpreter.cpp', output / 'interpreter.cpp.o'
    guard = json.loads((root / 'window-fp-guard/build.json').read_text())
    source_runtime.write_text((adapt_addze if args.addze else adapt)(original.read_text()))
    subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *guard['interpreterArguments'],
        '-c', str(source_runtime), '-o', str(object_runtime)], check=True, capture_output=True, timeout=60)
    original_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
    archive = output / 'libnwiiruntime.a'
    shutil.copy2(original_archive, archive)
    subprocess.run(['arch', '-arm64', '/usr/bin/ar', 'r', str(archive), str(object_runtime)], check=True, capture_output=True)
    subprocess.run(['arch', '-arm64', '/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
    retained = {}
    for member in subprocess.check_output(['arch', '-arm64', '/usr/bin/ar', 't', str(original_archive)], text=True).splitlines():
        if member == 'interpreter.cpp.o' or member.startswith('__.SYMDEF'):
            continue
        data = subprocess.check_output(['arch', '-arm64', '/usr/bin/ar', '-p', str(original_archive), member])
        assert data == subprocess.check_output(['arch', '-arm64', '/usr/bin/ar', '-p', str(archive), member])
        retained[member] = hashlib.sha256(data).hexdigest()
    command[command.index(str(original_archive))] = str(archive)
    runtime = {'originalSourceSha256': sha(original), 'sourceSha256': sha(source_runtime),
        'objectSha256': sha(object_runtime), 'archiveSha256': sha(archive),
        'originalArchiveSha256': sha(original_archive), 'retainedMembers': retained,
        'adapterSha256': sha(Path('experiments/wii-static-recomp/stock_interpreter_addze.py' if args.addze
            else 'experiments/wii-static-recomp/stock_interpreter_carry.py')),
        'carryAdapterSha256': sha(Path('experiments/wii-static-recomp/stock_interpreter_carry.py'))}
    game_command = list(command)
    game_exe = output / ('OpenSHSMStockInterpreterAddze' if args.addze else 'OpenSHSMStockInterpreterCarry')
    game_command[game_command.index('-o') + 1] = str(game_exe)
    subprocess.run(game_command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    (output / 'build.json').write_text(json.dumps({'linkCommand': game_command,
        'executableSha256': sha(game_exe), 'baseBuildSha256': sha(base / 'build.json'),
        'runtime': runtime}, indent=2) + '\n')
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'],
    '-c', str(source), '-o', str(obj)], check=True, capture_output=True, timeout=60)
full = root / 'window-quantization'
command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
command.insert(1, str(obj))
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
header = struct.unpack('>64I', dol[:256])
sites = []
selected = [(0x801988B4, 0x7C00F814), (0x801988BC, 0x7C03F914)]
if args.addze:
    selected.append((0x801E3938, 0x7EE00194))
for address, expected in selected:
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    opcode = struct.unpack('>I', dol[offset:offset + 4])[0]
    assert opcode == expected
    sites.append((address, opcode))
values = [0, 1, 2, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF]
cases = list(itertools.product(sites, values, values, [0, 0x20000000, 0x80000000, 0xE000007F]))
request = ''.join(f'{address} {opcode} {a} {b} {xer}\n' for (address, opcode), a, b, xer in cases)
result = subprocess.run([str(exe)], input=request, capture_output=True, text=True, timeout=30)
assert result.returncode == 0
(output / 'native.log').write_text(result.stdout + result.stderr)
rows = re.findall(r'^CARRY (\d+) (\d+) (\d+)$', result.stdout, re.M)
assert len(rows) == len(cases)
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
mismatches = []
for index, (((address, opcode), a, b, xer), row) in enumerate(zip(cases, rows)):
    registers = [0x12340000 + i * 256 for i in range(32)]
    registers[(opcode >> 16) & 31] = a
    if ((opcode >> 1) & 1023) != 202:
        registers[(opcode >> 11) & 31] = b
    scratch = 10
    registers[scratch] = xer
    for i, value in enumerate(registers):
        uc.reg_write(getattr(ppc, f'UC_PPC_REG_{i}'), value)
    setup = (31 << 26) | (scratch << 21) | (1 << 16) | (467 << 1)
    observe = (31 << 26) | (scratch << 21) | (1 << 16) | (339 << 1)
    uc.mem_write(address - 4, struct.pack('>III', setup, opcode, observe))
    uc.emu_start(address - 4, address + 8, count=3)
    expected = [uc.reg_read(getattr(ppc, f'UC_PPC_REG_{(opcode >> 21) & 31}')),
        uc.reg_read(getattr(ppc, f'UC_PPC_REG_{scratch}')), address + 4]
    actual = list(map(int, row))
    if actual != expected:
        mismatches.append({'case': index, 'address': f'{address:08X}', 'a': a, 'b': b,
            'xer': xer, 'expected': expected, 'actual': actual})
assert not mismatches if args.corrected else mismatches
report = {'result': 'ORIGINAL_DOL_INTERPRETER_CARRY_COMPONENT_PASS' if args.corrected
    else 'ORIGINAL_DOL_INTERPRETER_CARRY_DEFECT_REPRODUCED', 'cases': len(cases),
    'mismatches': mismatches, 'dolSha256': sha(dol_path), 'baseBuildSha256': sha(base / 'build.json'),
    'sourceSha256': sha(source), 'verifierSha256': sha(Path(__file__)), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'logSha256': sha(output / 'native.log'),
    'runtime': runtime,
    'linkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a')},
    'limits': ['Selected reached non-OE/non-Rc original instruction forms only; software 750CL oracle, not physical Wii.',
        'Component comparison does not establish the menu stop cause or repair full interpreter arithmetic; Rc/OE not validated here.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], len(cases), 'cases', len(mismatches), 'mismatches')
