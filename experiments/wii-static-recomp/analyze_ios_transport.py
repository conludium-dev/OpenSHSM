"""Pin the original SDK transport and compile its existing generated body in isolation."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess
import argparse
from compare_so_lowering import lower
from carry_lowering import lower as lower_carry

parser = argparse.ArgumentParser()
parser.add_argument('--compare-so', action='store_true')
parser.add_argument('--reply-handler', action='store_true')
parser.add_argument('--wakeup', action='store_true')
parser.add_argument('--select-thread', action='store_true')
parser.add_argument('--set-context', action='store_true')
parser.add_argument('--load-context', action='store_true')
parser.add_argument('--save-context', action='store_true')
parser.add_argument('--sleep', action='store_true')
parser.add_argument('--ipc-interrupt', action='store_true')
parser.add_argument('--irq-dispatch', action='store_true')
parser.add_argument('--exception-vector', action='store_true')
args = parser.parse_args()
assert sum((args.wakeup, args.reply_handler, args.select_thread, args.set_context, args.load_context, args.save_context, args.sleep, args.ipc_interrupt, args.irq_dispatch, args.exception_vector)) <= 1

private = Path('work/private-game/static-recomp')
output = private / ('ios-sleep' if args.sleep else 'ios-save-context' if args.save_context else 'ios-load-context' if args.load_context else 'ios-set-context' if args.set_context else 'ios-select-thread' if args.select_thread else 'ios-wakeup' if args.wakeup else 'ios-reply-handler' if args.reply_handler else 'ios-transport')
output.mkdir(exist_ok=True)
if args.ipc_interrupt:
    output = private / 'ios-ipc-interrupt'
    output.mkdir(exist_ok=True)
if args.irq_dispatch:
    output = private / 'ios-irq-dispatch'
    output.mkdir(exist_ok=True)
if args.exception_vector:
    output = private / 'ios-exception-vector'
    output.mkdir(exist_ok=True)
assembly_path = private / 'dtk-output/asm/auto_03_802045CC_text.s'
assembly = assembly_path.read_text()
entry, size, name = (0x80241CA0, 600, 'fn_80241CA0') if args.reply_handler else (0x802421F0, 576, '__ios_Ipc2')
if args.wakeup:
    entry, size, name = 0x8021B5D0, 248, 'fn_8021B5D0'
if args.select_thread:
    entry, size, name = 0x8021A790, 556, 'SelectThread'
if args.set_context:
    entry, size, name = 0x80213830, 92, 'OSSetCurrentContext'
if args.load_context:
    entry, size, name = 0x80213920, 216, 'OSLoadContext'
if args.save_context:
    entry, size, name = 0x802138A0, 128, 'fn_802138A0'
if args.sleep:
    entry, size, name = 0x8021B4E0, 240, 'OSSleepThread'
if args.ipc_interrupt:
    entry, size, name = 0x80241F00, 428, 'IPCInterruptHandler'
if args.irq_dispatch:
    entry, size, name = 0x80217C60, 80, 'ExternalInterruptHandler'
if args.exception_vector:
    entry, size, name = 0x80211BA0, 156, 'OSExceptionVector'
match = re.search(rf'# \.text:0x[0-9A-F]+ \| 0x{entry:08X} \| size: 0x{size:X}\n\.fn {name}, (?:local|global)\n(.*?)\.endfn {name}', assembly, re.S)
assert match
rows = re.findall(r'/\* ([0-9A-F]{8}) [0-9A-F]{8}  ([0-9A-F ]+) \*/\s*(.*)', match.group(1))
assert len(rows) == size // 4
expected_pcs = list(range(entry, entry + size, 4))
if args.irq_dispatch:
    dispatch = re.search(r'# \.text:0x133E4 \| 0x802179B0 \| size: 0x2A8\n\.fn fn_802179B0, global\n(.*?)\.endfn fn_802179B0', assembly, re.S)
    assert dispatch
    extra = re.findall(r'/\* ([0-9A-F]{8}) [0-9A-F]{8}  ([0-9A-F ]+) \*/\s*(.*)', dispatch.group(1))
    assert len(extra) == 170
    rows += extra
    expected_pcs += list(range(0x802179B0, 0x80217C58, 4))
    size += 680
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
original = {}
calls = []
for index, (pc, hexadecimal, disassembly) in enumerate(rows):
    pc = int(pc, 16)
    assert pc == expected_pcs[index]
    section = next(i for i in range(7) if header[18 + i] <= pc < header[18 + i] + header[36 + i])
    offset = header[section] + pc - header[18 + section]
    word = int.from_bytes(bytes.fromhex(hexadecimal), 'big')
    assert struct.unpack_from('>I', dol, offset)[0] == word
    original[pc] = word
    if word >> 26 == 18 and word & 1:
        displacement = word & 0x03FFFFFC
        if displacement & 0x02000000:
            displacement -= 0x04000000
        target = ((0 if word & 2 else pc) + displacement) & 0xFFFFFFFF
        calls.append({'pc': hex(pc), 'target': hex(target), 'dtkLabel': disassembly.split(maxsplit=1)[1]})
source = private / ('mass-current/output_63.cpp' if args.select_thread or args.set_context or args.load_context or args.save_context or args.irq_dispatch or args.exception_vector else 'mass-current/output_64.cpp' if args.wakeup or args.sleep else 'mass-current/output_67.cpp')
text = source.read_text()
start = text.index(f'void func_{entry:08X}(CPUContext& ctx) {{')
end = text.index('\nvoid func_', start + 1)
body = text[start:end]
markers = {int(pc, 16): int(word, 16) for pc, word in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body)}
skipped = {0x80211C38} if args.exception_vector else {0x8021B604} if args.wakeup else {0x8021B51C} if args.sleep else set()
assert markers == {pc: word for pc, word in original.items() if pc not in skipped}
changes = []
vector_changes = []
if args.exception_vector:
    fixes = [(0x80211BA0, '    // unhandled mtspr 272\n', '    ctx.sprg[0] = ctx.gpr[4];\n'),
             (0x80211BAC, '    std::cerr << "[WARN] mfspr r" << 3 << " spr=" << 272 << " (stub=0)\\n";\n    ctx.gpr[3] = 0; // unknown spr stub\n', '    ctx.gpr[3] = ctx.sprg[0];\n')]
    for address, before, after in fixes:
        marker = f'    // 0x{address:08X}: {original[address]:08X}\n'
        assert body.count(marker + before) == 1
        body = body.replace(marker + before, marker + after)
        vector_changes.append({'address': hex(address), 'opcode': hex(original[address]), 'before': before, 'after': after})
if args.compare_so:
    body, changes = lower(body, dol)
    assert changes
carry_changes = []
if args.wakeup or args.select_thread:
    body, carry_changes = lower_carry(body, dol)
    assert len(carry_changes) == (2 if args.select_thread else 1)
generated = output / 'selected.cpp'
generated.write_text(text[:text.index('void func_')] + ('#include "carry_adapter.h"\n' if args.wakeup or args.select_thread else '') + body)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/include')
obj = output / 'transport.o'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(upstream),
                         '-I', str(private / 'mass-current'), '-I', 'experiments/wii-static-recomp', '-c', str(generated), '-o', str(obj)],
                        capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
expected = {0x8021A440, 0x80212FD0, 0x802174E0, 0x80217520, 0x802438B0,
            0x80243B60, 0x80241C30, 0x80241C20, 0x8021B4E0}
if not any((args.reply_handler, args.wakeup, args.select_thread, args.set_context, args.load_context, args.save_context, args.sleep, args.ipc_interrupt, args.irq_dispatch, args.exception_vector)):
    assert {int(row['target'], 16) for row in calls} == expected, calls
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': f'ORIGINAL_IOS_{"SLEEP" if args.sleep else "SAVE_CONTEXT" if args.save_context else "LOAD_CONTEXT" if args.load_context else "SET_CONTEXT" if args.set_context else "SELECT_THREAD" if args.select_thread else "WAKEUP" if args.wakeup else "REPLY_HANDLER" if args.reply_handler else "TRANSPORT"}{size // 4}_DOL_WORDS_NATIVE_OBJECT_PASS',
          'entry': hex(entry), 'bytes': size, 'instructions': size // 4, 'calls': calls,
          'generatedInstructions': len(markers), 'skippedNopAddresses': [hex(pc) for pc in sorted(skipped)],
          'dolSha256': sha(dol_path), 'assemblySha256': sha(assembly_path),
          'parentGeneratedSha256': sha(source), 'generatedSha256': sha(generated),
          'objectSha256': sha(obj), 'scriptSha256': sha(Path(__file__)),
          'compareSoChanges': changes,
          'carryChanges': carry_changes,
          'compareSoLoweringSha256': sha(Path('experiments/wii-static-recomp/compare_so_lowering.py')),
          'limits': ['SDK labels inherited from dtk signatures, not retained original debug symbols.',
                     'Static direct-call dependencies and compilation only; branch execution/order/ABI not verified.',
                     'No original transport execution, IOS completion, cache visibility, thread/IRQ or boot activation.']}
if args.ipc_interrupt:
    report['result'] = 'ORIGINAL_IPC_INTERRUPT107_DOL_WORDS_NATIVE_OBJECT_PASS'
if args.exception_vector:
    report['result'] = 'ORIGINAL_EXCEPTION_VECTOR39_DOL_WORDS38_NATIVE_INSTRUCTIONS_PASS'
    report['sprgLowerings'] = vector_changes
    report['copiedBytes'] = 152
    report['limits'].append('Template ID instruction remains0; original initializer patches the ID before copying152bytes. SPRG0 lowerings private only; relocated vector execution not verified.')
if args.irq_dispatch:
    report['result'] = 'ORIGINAL_EXTERNAL_IRQ_DISPATCH190_DOL_WORDS_NATIVE_OBJECT_PASS'
    report['components'] = [{'entry': '0x80217c60', 'name': name, 'bytes': 80},
                            {'entry': '0x802179b0', 'name': 'fn_802179B0', 'bytes': 680}]
    report['limits'].append('Dispatcher meaning inferred from original source; generated body inlines two dtk functions, not a contiguous760-byte span.')
    facts = {0x80217B88: 0x57E30463, 0x80217B90: 0x60000010,
             0x80242120: 0x3860001B, 0x80242124: 0x38841F00, 0x80242128: 0x4BFD5429,
             0x8024212C: 0x38600010, 0x80242130: 0x4BFD5801,
             0x8021759C: 0x387F3040, 0x802175A8: 0x906DC3B8}
    for pc, word in facts.items():
        section = next(i for i in range(7) if header[18 + i] <= pc < header[18 + i] + header[36 + i])
        offset = header[section] + pc - header[18 + section]
        assert struct.unpack_from('>I', dol, offset)[0] == word
    report['ipcRouting'] = {'piCauseBit': '0x4000', 'softwareMaskBit': '0x10', 'interruptIndex': 27,
                            'handler': '0x80241f00', 'handlerTableBase': '0x80003040', 'ipcSlot': '0x800030ac',
                            'evidenceWords': {hex(pc): hex(word) for pc, word in facts.items()},
                            'status': 'Original DOL instructions; effective installed table/masks and runtime dispatch unverified.'}
(output / 'analysis.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS original {name}:{size // 4}instructions/DOL bytes/native object; service execution remains pending')
