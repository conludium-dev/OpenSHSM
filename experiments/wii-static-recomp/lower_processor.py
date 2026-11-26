"""Verified instruction-lowering override over existing mass output; do not edit game logic by hand."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import subprocess
import shlex
import concurrent.futures
from carry_lowering import lower as lower_carry

parser = argparse.ArgumentParser()
parser.add_argument('--cache', action='store_true')
parser.add_argument('--stock', action='store_true')
parser.add_argument('--carry', action='store_true')
args = parser.parse_args()
assert not (args.stock and args.cache)
assert not args.carry or args.stock
base = Path('work/private-game/static-recomp/mass-current')
output = Path('work/private-game/static-recomp/mass-cache' if args.cache else 'work/private-game/static-recomp/mass-processor')
if args.stock:
    base = Path('work/private-game/static-recomp/stock-baseline/window-optimized')
    output = base.parent / ('window-hid2-carry' if args.carry else 'window-hid2')
output.mkdir(exist_ok=True)
experiment = Path('experiments/wii-static-recomp')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
generation_path = base / ('build.json' if args.stock else 'generation.json')
generation = json.loads(generation_path.read_text())
if args.stock:
    generation['generatedSha256'] = {f"output_{item['index']}.cpp": item['sourceSha256'] for item in generation['modules']}
    flags = (base.parent / 'export/build/CMakeFiles/OpenSHSMStockBaseline.dir/flags.make').read_text()
    compiler = re.search(r'# compile CXX with (.+)', flags)[1]
    compile_args = []
    for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
        compile_args += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
    compile_args += ['-O2', '-fno-strict-aliasing', '-fwrapv', '-ffp-contract=off', '-I', str(base), '-I', str(base.parent / 'export')]
    assert not any(flag in compile_args for flag in ('-DNDEBUG', '-ffast-math', '-Ofast'))
    if args.carry:
        carry_header = (experiment / 'carry_adapter.h').read_text()
        assert carry_header.count('#include "l2_adapter.h"') == 1
        (output / 'carry_adapter.h').write_text(carry_header.replace('#include "l2_adapter.h"', '#include "runtime/cpu_context.h"'))
        compile_args += ['-include', str(output / 'carry_adapter.h')]
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
changes = []
files = []
jobs = []
carry_changes = []
for name, digest in generation['generatedSha256'].items():
    source = base / name
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    lines = source.read_text().splitlines(True)
    changed = False
    for index, line in enumerate(lines):
        match = re.search(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', line)
        if not match:
            continue
        address, opcode = [int(value, 16) for value in match.groups()]
        if opcode >> 26 != 31 or ((opcode >> 1) & 1023) not in (339, 467):
            continue
        spr = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
        if spr not in ({920, 1008} if args.cache else {920}):
            continue
        section = next(section for section in range(18) if header[18 + section] <= address < header[18 + section] + header[36 + section])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        register = (opcode >> 21) & 31
        write = ((opcode >> 1) & 1023) == 467
        prior = lines[index + 1]
        label = 'hid2' if spr == 920 else 'hid0'
        if write:
            assert prior.strip() == f'// unhandled mtspr {spr}'
            replacement = f'    nwii::runtime::experiment_write_{label}(ctx, ctx.gpr[{register}]);\n'
        else:
            expected = f'ctx.gpr[{register}] = 0; // mfspr HID 920' if spr == 920 else f'ctx.gpr[{register}] = 0; // mfspr HID0 (stub)'
            assert prior.strip() == expected
            replacement = f'    ctx.gpr[{register}] = nwii::runtime::experiment_read_{label}(ctx);\n'
        lines[index + 1] = replacement
        changed = True
        changes.append({'file': name, 'address': hex(address), 'opcode': hex(opcode),
                        'spr': spr,
                        'operation': 'write' if write else 'read', 'register': register,
                        'priorLowering': prior.strip(), 'adapterLowering': replacement.strip()})
    text = ''.join(lines)
    if args.carry:
        text, numeric_changes = lower_carry(text, dol, stock=True)
        carry_changes.extend(dict(item, file=name) for item in numeric_changes)
        changed = changed or bool(numeric_changes)
    if changed:
        target = output / name
        target.write_text(text)
        obj = output / (name + '.o')
        command = [compiler, *compile_args, '-include', str(experiment / 'processor_adapter.h'), '-c', str(target), '-o', str(obj)] if args.stock else ['clang++', '-std=c++20', '-O0', '-include', str(experiment / 'processor_adapter.h'),
                                 '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(base),
                                 '-c', str(target), '-o', str(obj)]
        jobs.append((name, digest, target, obj, command))

def compile_job(job):
    name, digest, target, obj, command = job
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    (output / (name + '.build.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-4000:]
    print('Compiled', name, flush=True)
    return {'file': name, 'baseSha256': digest, 'sourceSha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'objectSha256': hashlib.sha256(obj.read_bytes()).hexdigest()}

with concurrent.futures.ThreadPoolExecutor(max_workers=3 if args.stock else 1) as pool:
    files = list(pool.map(compile_job, jobs))
assert changes and files
report = {'result': 'PASS', 'scope': 'Selected processor instruction-lowering overrides; register/boot behavior verified separately.',
          'files': files, 'changes': changes, 'baseGenerationSha256': hashlib.sha256(generation_path.read_bytes()).hexdigest(),
          'adapterHeaderSha256': hashlib.sha256((experiment / 'processor_adapter.h').read_bytes()).hexdigest(),
          'adapterSourceSha256': hashlib.sha256((experiment / 'processor_adapter.cpp').read_bytes()).hexdigest(),
          'loweringScriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'source': 'Dolphin Interpreter_SystemRegisters.cpp SPR_HID2 read/write policy; sources recorded in README.',
          'limits': ['Original flow/opcodes/other translations preserved; no full regeneration or manually recovered game-function bodies.',
                     'ProcessorContext extends the existing CPUContext; helper contract requires a live ProcessorContext instance.',
                     'HID2 register bits only: locked-cache/DMA/gather-pipe consumers and privileged exception delivery remain unimplemented.']}
(output / 'lowering.json').write_text(json.dumps(report, indent=2) + '\n')
if args.carry:
    report['carryChanges'] = carry_changes
    report['carryHeaderSha256'] = hashlib.sha256((output / 'carry_adapter.h').read_bytes()).hexdigest()
    report['carryBaseHeaderSha256'] = hashlib.sha256((experiment / 'carry_adapter.h').read_bytes()).hexdigest()
    report['carryLoweringSha256'] = hashlib.sha256((experiment / 'carry_lowering.py').read_bytes()).hexdigest()
    (output / 'lowering.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Carry sites:', len(carry_changes), flush=True)
print('PASS:lowering only;', len(changes), 'original processor sites in', len(files), 'batches; base sources/objects unchanged')
