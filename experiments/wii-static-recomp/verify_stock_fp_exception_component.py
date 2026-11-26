"""Run original relocated vector and recompiled SDK on the current stock CPU/MMU."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import subprocess
from stock_fp_unavailable_patch import adapt_interpreter
from stock_fp_context_patch import adapt_lazy_fp_context
from stock_fp_guard_lowering import lower

parser = argparse.ArgumentParser()
parser.add_argument('--lazy-context', action='store_true')
parser.add_argument('--nonlocal', dest='nonlocal_transfer', action='store_true')
args = parser.parse_args()
assert not args.nonlocal_transfer or args.lazy_context

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-quantization'
output = root / ('fp-exception-nonlocal-component' if args.nonlocal_transfer
    else 'fp-exception-lazy-component' if args.lazy_context else 'fp-exception-component')
output.mkdir(exist_ok=True)
public = Path('experiments/wii-static-recomp').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol').resolve()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
def dol_word(address):
    section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    return struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0]

text = (base / 'output_38.cpp').read_text()
classification = json.loads((root / 'fp-guard-component/report.json').read_text()) if args.nonlocal_transfer else None
selected = '#include <iostream>\n#include <bit>\nusing namespace nwii::runtime;\n'
selected += 'namespace nwii::runtime { extern bool g_trace_calls; void trace_call(uint32_t, CPUContext&); }\n'
entries = [0x802135C0, 0x802136F0, 0x80213DC0]
if args.lazy_context:
    entries += [0x80213920]
selected += ''.join(f'void func_{entry:08X}(CPUContext&);\n' for entry in entries)
sites = []
for entry in entries:
    start = text.index(f'void func_{entry:08X}(CPUContext& ctx) {{')
    end = text.index('\nvoid func_', start + 1)
    body = text[start:end]
    for address, opcode in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body):
        assert dol_word(int(address, 16)) == int(opcode, 16)
        sites.append({'address': address, 'opcode': opcode})
    assert body.count('    // mtfsf stub (ignore FPSCR write)\n') == (entry == 0x802135C0)
    assert body.count('    ctx.fpr[0] = 0.0; // mffs stub\n') == (entry == 0x802136F0)
    if args.nonlocal_transfer:
        body, guards, fpscr = lower(body, dol, classification['tables'])
    body = body.replace('    // mtfsf stub (ignore FPSCR write)\n',
                        '    experiment_mtfsf(ctx, 0xFDFE058E);\n')
    body = body.replace('    ctx.fpr[0] = 0.0; // mffs stub\n',
                        '    ctx.fpr[0] = std::bit_cast<double>(uint64_t(ctx.fpscr));\n')
    selected += body + '\n'
assert dol_word(0x802135D0) == 0xFDFE058E and dol_word(0x8021377C) == 0xFC00048E
assert dol_word(0x8020AFD4) == 0xDBE10070
store_source = base / 'output_37.cpp'
store_text = store_source.read_text()
store = re.search(r'// 0x8020AFD4: DBE10070\n(.*?)loc_8020AFD8: ;', store_text, re.S).group(1)
assert store.count('ctx.mmu.write_f64(ctx.gpr[1] + 112, ctx.fpr[31]);') == 1
selected += 'void guarded_original_stfd(CPUContext& ctx) {\n'
selected += ('    stock_fp_preinstruction(ctx, 0xDBE10070, 0x8020AFD4);\n' if args.nonlocal_transfer
    else '    if (!stock_scalar_fp_available(ctx, 0x8020AFD4)) { return; }\n')
selected += store + '    ctx.pc = 0x8020AFD8;\n}\n'
vector = [dol_word(0x80211BA0 + i * 4) for i in range(38)]
assert vector[0] == 0x7C9043A6 and vector[3] == 0x7C7042A6 and vector[26] == 0x38600000
(output / 'selected-fpu.h').write_text(selected)
extra_inputs = []
if args.lazy_context:
    old_ios = root / 'window-fp-context/ios.cpp'
    old = old_ios.read_text()
    adapted = adapt_lazy_fp_context(old)
    new_ios = output / 'ios.cpp'
    new_ios.write_text(adapted)
    header = output / 'context-helpers.h'
    helpers = ''
    for label, body in [('baseline', old), ('lazy', adapted)]:
        start = body.index('static void hle_save_context_to_guest(')
        end = body.index('int g_trace_after_dec', start)
        helpers += body[start:end].replace('hle_save_context_to_guest', label + '_save').replace('hle_load_context_from_guest', label + '_load')
    header.write_text(helpers)
    extra_inputs = [old_ios, new_ios, header, Path('experiments/wii-static-recomp/stock_fp_context_patch.py').resolve()]
interpreter = output / 'interpreter.cpp'
interpreter.write_text(adapt_interpreter((base / 'interpreter.cpp').read_text(), complete=args.nonlocal_transfer))
source = public / 'stock_fp_unavailable_contract.cpp'
exe = output / 'fp-exception-contract'
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
    '-I', str(base / 'include'), '-I', str(base), '-I', str(output), '-I', str(public),
    str(source), str(interpreter), '-o', str(exe)]
if args.lazy_context:
    command.insert(1, '-DSTOCK_LAZY_CONTEXT')
if args.nonlocal_transfer:
    command.insert(1, '-DSTOCK_NONLOCAL_CONTEXT')
result = subprocess.run(command, capture_output=True, text=True, timeout=60)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe), str(dol_path)], capture_output=True, text=True, timeout=20)
(output / 'run.log').write_text(result.stdout + result.stderr)
if result.returncode != 0:
    (output / 'negative-result.json').write_text(json.dumps({'returncode': result.returncode,
        'stdout': result.stdout, 'stderr': result.stderr, 'executableSha256': sha(exe),
        'sourceSha256': sha(source), 'selectedSha256': sha(output / 'selected-fpu.h'),
        'interpreterSha256': sha(interpreter)}, indent=2) + '\n')
assert result.returncode == 0, result.stdout + result.stderr
assert not result.stderr and '[Interp]' not in result.stdout
paths = [source, interpreter, output / 'selected-fpu.h', base / 'output_38.cpp',
    store_source,
    base / 'interpreter.cpp', base / 'include/runtime/cpu_context.h', base / 'processor_adapter.h',
    public / 'stock_fp_unavailable.h', public / 'stock_fp_unavailable_patch.py',
    public / 'fpscr_adapter.h', public / 'stock_quantization_contract.cpp', Path(__file__).resolve(), exe] + extra_inputs
if args.nonlocal_transfer:
    paths += [root / 'fp-guard-component/report.json', public / 'stock_fp_guard_lowering.py']
report = {'result': 'LAZY_HLE_FP_EXCEPTION_SDK_COMPONENT_PASS' if args.lazy_context else 'SCALAR_FP_EXCEPTION_SDK_COMPONENT_PASS', 'output': result.stdout.strip(),
    'dolSha256': sha(dol_path), 'compileCommand': command,
    'inputs': [{'path': str(path), 'sha256': sha(path)} for path in paths],
    'sdkInstructions': sites, 'vectorWords': [hex(value) for value in vector],
    'lazyContext': args.lazy_context,
    'nonlocalTransfer': args.nonlocal_transfer,
    'pcAdaptations': ['Flat existing MMU aliases physical vector800 and high80000800.',
        'Vector installation/context initialization are fixtures; original vector ID patched7 as SDK initializer does.',
        'Existing interpreter scalar48..55 guard and SPRG272..275; no general PPC guard integrated.',
        'SDK generated mtfsf uses existing adapter; mffs boxed raw FPSCR replaces original translator stub.'],
    'limits': ['No original Wii/Dolphin dynamic oracle in this test; DOL instruction checks and primary mask reference only.',
        'Finite GQR0=0, HID2.PSE enabled, FPSCR0; arbitrary FPSCR/NaN/subnormal/program exceptions unverified.',
        'Callback function is isolated false stub; full IOS HLE save/load/ownership and longjmp not integrated.',
        'No guest boot, pixel/menu acceptance, production build or release changes.']}
(output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout.strip(), 'DOL SDK instructions=', len(sites))
