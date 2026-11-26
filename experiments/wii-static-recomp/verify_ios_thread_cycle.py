"""Compare two prepared threads through original sleep/selection/wakeup/resumption."""
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
import ctypes
from compare_so_lowering import lower
from carry_lowering import lower as lower_carry

parser = argparse.ArgumentParser()
parser.add_argument('--original-irqs', action='store_true')
parser.add_argument('--deferred-wakeup', action='store_true')
parser.add_argument('--reply-handler', action='store_true')
parser.add_argument('--kernel-reply', action='store_true')
parser.add_argument('--transport', action='store_true')
parser.add_argument('--open-lifecycle', action='store_true')
parser.add_argument('--heap-reuse', action='store_true')
parser.add_argument('--allocation-failure', action='store_true')
parser.add_argument('--ipc-interrupt', action='store_true')
parser.add_argument('--ipc-ack', action='store_true')
parser.add_argument('--ipc-registers', action='store_true')
parser.add_argument('--ipc-control', action='store_true')
parser.add_argument('--ipc-irq', action='store_true')
parser.add_argument('--external-irq', action='store_true')
parser.add_argument('--exception-vector', action='store_true')
parser.add_argument('--vector-return', action='store_true')
parser.add_argument('--drop-event-mutant', action='store_true')
parser.add_argument('--drop-after-reuse', action='store_true')
parser.add_argument('--drop-after-ack', action='store_true')
args = parser.parse_args()
args.exception_vector |= args.vector_return
args.external_irq |= args.exception_vector
args.ipc_irq |= args.external_irq
args.ipc_control |= args.ipc_irq
args.ipc_registers |= args.ipc_control
args.ipc_ack |= args.ipc_registers
args.ipc_interrupt |= args.ipc_ack
args.open_lifecycle |= args.heap_reuse or args.allocation_failure or args.ipc_interrupt
assert not args.ipc_interrupt or not (args.heap_reuse or args.allocation_failure)
assert not args.allocation_failure or not (args.heap_reuse or args.drop_event_mutant)
args.transport |= args.open_lifecycle
assert not args.drop_event_mutant or args.transport
assert not args.drop_after_reuse or args.drop_event_mutant and args.heap_reuse
assert not args.drop_after_ack or args.drop_event_mutant and args.ipc_ack
args.kernel_reply |= args.transport
args.reply_handler |= args.kernel_reply
args.deferred_wakeup |= args.reply_handler
args.original_irqs |= args.deferred_wakeup

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ
from unicorn import ppc_const as ppc

private = Path('work/private-game/static-recomp')
output = private / ('ios-thread-cycle-open-failure' if args.allocation_failure else 'ios-thread-cycle-open-reuse' if args.heap_reuse else 'ios-thread-cycle-open' if args.open_lifecycle else 'ios-thread-cycle-transport' if args.transport else 'ios-thread-cycle-kernel' if args.kernel_reply else 'ios-thread-cycle-reply' if args.reply_handler else 'ios-thread-cycle-deferred' if args.deferred_wakeup else 'ios-thread-cycle-irqs' if args.original_irqs else 'ios-thread-cycle')
output.mkdir(exist_ok=True)
if args.ipc_interrupt:
    output = private / ('ios-thread-cycle-external-irq' if args.external_irq else 'ios-thread-cycle-ipc-irq' if args.ipc_irq else 'ios-thread-cycle-ipc-control' if args.ipc_control else 'ios-thread-cycle-ipc-registers' if args.ipc_registers else 'ios-thread-cycle-ipc-ack' if args.ipc_ack else 'ios-thread-cycle-ipc-interrupt')
    output.mkdir(exist_ok=True)
if args.drop_event_mutant:
    output = output / ('drop-after-ack-mutant' if args.drop_after_ack else 'drop-reused-event-mutant' if args.drop_after_reuse else 'drop-event-mutant')
    output.mkdir(exist_ok=True)
if args.exception_vector:
    output = private / ('ios-thread-cycle-vector-return' if args.vector_return else 'ios-thread-cycle-vector')
    if args.drop_event_mutant:
        output /= 'drop-after-ack-mutant' if args.drop_after_ack else 'drop-event-mutant'
    output.mkdir(parents=True, exist_ok=True)
sources = []
for mode in ('sleep', 'wakeup', 'select-thread', 'set-context', 'save-context', 'load-context', *(['reply-handler'] if args.reply_handler else []), *(['transport'] if args.transport else []), *(['ipc-interrupt'] if args.ipc_interrupt else []), *(['irq-dispatch'] if args.external_irq else [])):
    command = ['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', *([] if mode == 'transport' else ['--' + mode])]
    if mode in ('sleep', 'wakeup', 'select-thread', 'set-context', 'reply-handler', 'transport', 'ipc-interrupt', 'irq-dispatch'):
        command.append('--compare-so')
    prepared = subprocess.run(command, capture_output=True, text=True, timeout=180)
    assert prepared.returncode == 0, prepared.stderr[-2000:]
    sources.append(private / ('ios-' + mode) / 'selected.cpp')
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])


def original_word(address):
    i = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    return struct.unpack_from('>I', dol, header[i] + address - header[18 + i])[0]


assert original_word(0x80528A30) == 0x8021A1A0
parent = (private / 'mass-current/output_63.cpp').read_text()
helpers = []
helper_sizes = {0x80213890: 3, 0x8021A1A0: 1}
if args.original_irqs:
    helper_sizes.update({0x802174E0: 5, 0x80217520: 9})
if args.deferred_wakeup:
    helper_sizes[0x8021A9C0] = 144
if args.transport:
    helper_sizes[0x8021A440] = 4
if args.external_irq:
    helper_sizes.update({0x8021A460: 15, 0x8021A4A0: 15})
irq_changes = []
for entry, count in helper_sizes.items():
    start = parent.index(f'void func_{entry:08X}(CPUContext& ctx) {{')
    end = parent.index('\nvoid func_', start + 1)
    body = parent[start:end]
    markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body)
    expected_pcs = list(range(0x8021A790, 0x8021A9BC, 4)) + list(range(0x8021A9C0, 0x8021A9D4, 4)) if entry == 0x8021A9C0 else list(range(entry, entry + count * 4, 4))
    assert len(markers) == count and [int(pc, 16) for pc, word in markers] == expected_pcs
    assert all(original_word(int(pc, 16)) == int(word, 16) for pc, word in markers)
    if entry in (0x802174E0, 0x80217520, 0x8021A9C0):
        body, changes = lower(body, dol)
        irq_changes.extend(changes)
    if entry == 0x8021A9C0:
        body, carry_changes = lower_carry(body, dol)
        assert len(carry_changes) == 2
    helpers.append(body)
helper = output / 'helpers.cpp'
helper.write_text(parent[:parent.index('void func_')] + ('#include "carry_adapter.h"\n' if args.deferred_wakeup else '') + '\n'.join(helpers))
sources.append(helper)
analysis_sources = list(sources[:-1])
if args.ipc_registers:
    register_parent = (private / 'mass-current/output_67.cpp').read_text()
    register_bodies = []
    for entry in (0x80241C20, 0x80241C30):
        start = register_parent.index(f'void func_{entry:08X}(CPUContext& ctx) {{')
        end = register_parent.index('\nvoid func_', start + 1)
        body = register_parent[start:end]
        markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body)
        assert [int(pc, 16) for pc, word in markers] == list(range(entry, entry + 16, 4))
        assert all(original_word(int(pc, 16)) == int(word, 16) for pc, word in markers)
        register_bodies.append(body)
    register_source = output / 'ipc-registers.cpp'
    register_source.write_text(register_parent[:register_parent.index('void func_')] + '\n'.join(register_bodies))
    sources.append(register_source)
if args.open_lifecycle:
    open_parent = (private / 'mass-current/output_67.cpp').read_text()
    open_bodies = []
    for entry in (0x80242550, 0x80243570, 0x802438A0, 0x802438B0):
        start = open_parent.index(f'void func_{entry:08X}(CPUContext& ctx) {{')
        end = open_parent.index('\nvoid func_', start + 1)
        open_bodies.append(open_parent[start:end])
    open_body = '\n'.join(open_bodies)
    open_markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', open_body)
    expected = (set(range(0x80242550, 0x80242674, 4)) - {0x802425FC})
    expected |= set(range(0x80243570, 0x8024389C, 4)) | {0x802438A0}
    expected |= set(range(0x802438B0, 0x80243A98, 4)) - {0x80243964}
    assert len(open_markers) == len(expected) and {int(pc, 16) for pc, word in open_markers} == expected
    assert all(original_word(int(pc, 16)) == int(word, 16) for pc, word in open_markers)
    open_body, open_so_changes = lower(open_body, dol)
    open_body, open_carry_changes = lower_carry(open_body, dol)
    open_source = output / 'open-allocator-free.cpp'
    open_source.write_text(open_parent[:open_parent.index('void func_')] + '#include "carry_adapter.h"\n' + open_body)
    sources.append(open_source)
kernel_sources = []
if args.kernel_reply:
    upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
    kernel = private / 'ipc-kernel-fixed/ios_kernel.cpp'
    assert kernel.read_text() == (upstream / 'src/hle/ios_kernel.cpp').read_text().replace('    return IPC_ENOENT;', '    return -6;')
    kernel_sources = [kernel, upstream / 'src/core/event_scheduler.cpp']
host = Path('experiments/wii-static-recomp/ios_thread_cycle_host.cpp')
if args.ipc_control:
    subprocess.run(['python3', 'experiments/wii-static-recomp/verify_ipc_control_backend.py'], check=True)
    kernel_sources += [upstream / 'src/hw/hw_pi.cpp', upstream / 'src/hw/mmio_dispatcher.cpp']
if args.ipc_irq:
    subprocess.run(['python3', 'experiments/wii-static-recomp/verify_ipc_irq_backend.py'], check=True)
priority_words = [original_word(0x8042CF98 + i * 4) for i in range(12)] if args.external_irq else []
vector_words = []
if args.exception_vector:
    prepared_vector = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--exception-vector'], capture_output=True, text=True, timeout=180)
    assert prepared_vector.returncode == 0, prepared_vector.stderr[-2000:]
    vector_parent = private / 'ios-exception-vector/selected.cpp'
    vector_body = vector_parent.read_text()
    before = '    // 0x80211C08: 38600000\n    ctx.gpr[3] = 0; // li r3, 0\n'
    assert vector_body.count(before) == 1
    vector_body = vector_body.replace(before, '    // 0x80211C08: 38600000\n    if (ctx.mmu.read32(0x80000568) != 0x38600004) { throw std::runtime_error("Unverified relocated vector ID"); }\n    ctx.gpr[3] = ctx.mmu.read32(0x80000568) & 0xffffu;\n')
    vector_source = output / 'vector.cpp'
    vector_source.write_text('#include <stdexcept>\n' + vector_body)
    sources.append(vector_source)
    vector_words = [original_word(0x80211BA0 + i * 4) for i in range(38)]
exe = output / 'thread-cycle-host'
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-Wl,-dead_strip',
                        '-DSHSM_ORIGINAL_ALLOCATOR', '-I', '_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/include',
                        *(['-DSHSM_ORIGINAL_IRQ_SERVICES', '-DSHSM_EMPTY_IRQ_FIXTURE'] if args.original_irqs else []),
                        *(['-DSHSM_DEFERRED_WAKEUP'] if args.deferred_wakeup else []),
                        *(['-DSHSM_THREAD_REPLY_HANDLER', '-DSHSM_REPLY_HANDLER'] if args.reply_handler else []),
                        *(['-DSHSM_THREAD_KERNEL_REPLY'] if args.kernel_reply else []),
                        *(['-DSHSM_THREAD_TRANSPORT', '-DSHSM_ORIGINAL_TRANSPORT'] if args.transport else []),
                        *(['-DSHSM_THREAD_OPEN'] if args.open_lifecycle else []),
                        *(['-DSHSM_THREAD_HEAP_REUSE'] if args.heap_reuse else []),
                        *(['-DSHSM_THREAD_ALLOCATION_FAILURE'] if args.allocation_failure else []),
                        *(['-DSHSM_THREAD_IPC_INTERRUPT'] if args.ipc_interrupt else []),
                        *(['-DSHSM_THREAD_IPC_ACK'] if args.ipc_ack else []),
                        *(['-DSHSM_ORIGINAL_IPC_REGISTERS'] if args.ipc_registers else []),
                        *(['-DSHSM_THREAD_IPC_CONTROL', '-I', str(upstream / 'src/hw')] if args.ipc_control else []),
                        *(['-DSHSM_THREAD_IPC_IRQ'] if args.ipc_irq else []),
                        *(['-DSHSM_THREAD_EXTERNAL_IRQ'] if args.external_irq else []),
                        *(['-DSHSM_THREAD_EXCEPTION_VECTOR'] if args.exception_vector else []),
                        *(['-DSHSM_THREAD_VECTOR_RETURN'] if args.vector_return else []),
                        *(['-DSHSM_DROP_THREAD_REPLY'] if args.drop_event_mutant else []),
                        *(['-DSHSM_DROP_AFTER_REUSE'] if args.drop_after_reuse else []),
                        *(['-DSHSM_DROP_AFTER_ACK'] if args.drop_after_ack else []),
                        '-I', 'experiments/wii-static-recomp', '-I', str(private / 'mass-current'), str(host),
                        *map(str, sources + kernel_sources), '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-2000:]
cases = [pair + rest for pair in ((0, 7), (0, 31), (7, 31))
         for rest in itertools.product([0, 1, 2], [0, 0x2000], [0, 0xA0000000], [0, 2])]
if args.original_irqs:
    cases += [case[:3] + (case[3] | 0x8000,) + case[4:] for case in cases]
if args.exception_vector:
    cases += [case[:3] + (case[3] | 0x30,) + case[4:] for case in cases]
native = subprocess.run([str(exe.resolve())], input=''.join(' '.join(map(str, (*case, *priority_words, *vector_words))) + '\n' for case in cases),
                        capture_output=True, text=True, timeout=60)
(output / 'native.log').write_text(native.stdout + native.stderr)
if args.drop_event_mutant:
    assert native.returncode == 9 and 'THREAD_TRANSPORT_LOST_REPLY_DETECTED' in native.stdout, native.stderr[-2000:]
    if args.drop_after_ack:
        assert 'THREAD_ACK_WITHOUT_REPLY_DETECTED' in native.stdout
        print('THREAD_ACK_WITHOUT_REPLY_DETECTED')
    print('THREAD_TRANSPORT_LOST_REPLY_DETECTED')
    sys.exit(9)
assert native.returncode == 0, native.stderr[-2000:]
rows = [row.split() for row in native.stdout.splitlines() if not row.startswith('[IOSKernel] ')]
phase_count = 5 if args.vector_return else 4 if args.ipc_ack else 1 if args.allocation_failure else 3 if args.deferred_wakeup else 2
assert len(rows) == len(cases) * phase_count
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
if args.exception_vector:
    subprocess.run(['python3', 'experiments/wii-static-recomp/verify_bat_seed.py'], check=True)
    bat_seed_path = private / 'dolphin-bat-seed/seed.json'
    bat_seed = json.loads(bat_seed_path.read_text())
    oracle_backing = []
    for addresses, size in (((0, 0x80000000), 24 * 1024 * 1024), ((0x0C000000, 0xCC000000), 65536), ((0x0D000000, 0xCD000000), 4096)):
        buffer = ctypes.create_string_buffer(size)
        oracle_backing.append(buffer)
        for address in addresses:
            uc.mem_map_ptr(address, size, 7, ctypes.addressof(buffer))
else:
    uc.mem_map(0x80000000, 24 * 1024 * 1024)
    if args.reply_handler:
        uc.mem_map(0xCD000000, 4096)
    if args.external_irq:
        uc.mem_map(0xCC000000, 65536)
for i in range(18):
    if header[36 + i]:
        uc.mem_write(header[18 + i], dol[header[i]:header[i] + header[36 + i]])
regs = [getattr(ppc, f'UC_PPC_REG_{i}') for i in range(32)]
store = lambda address, value: uc.mem_write(address, struct.pack('>I', value))
load = lambda address: struct.unpack('>I', uc.mem_read(address, 4))[0]
spans = [(0x80680000, 1024), (0x80690000, 1024), (0x806A004C, 8), (0x80492970, 256),
         (0x8052AB00, 12), (0x800000C0, 28), (0x800000E4, 4), (0x806FFF80, 160), (0x806FEF80, 160)]
if args.reply_handler:
    spans[2] = (0x806A0020, 64)
    spans[-1] = (0x806FEC80, 928)
if args.transport:
    spans += [(0x804B2A80, 80), (0x80528B70, 8)]
if args.open_lifecycle:
    spans[2] = (0x806A0000, 4096)
    spans.append((0x804B2B40, 128))
if args.ipc_ack:
    spans.append((0x8052AFD8, 8))
if args.ipc_control:
    spans.append((0x806A1200, 32 if args.ipc_irq else 24))
if args.external_irq:
    spans += [(0x80003040, 128), (0x8042CF98, 48), (0x8052AAC8, 20)]
if args.exception_vector:
    spans += [(0x80000500, 152), (0x80003000, 64)]
if args.vector_return:
    spans.append((0x806A1300, 8))
events = []
ipc_control = 0x30
ipc_message = ipc_arm_message = 0
ipc_flags = 0
ipc_cause = 0x10000
reply_pending = False
external_boundary = False
if args.kernel_reply:
    oracle_path = private / 'dolphin-ipc-packet/comparison.json'
    reply_header = bytes.fromhex(json.loads(oracle_path.read_text())['observations'][0]['replyPacketHex'])[:12]
    assert struct.unpack('>III', reply_header) == (8, 0xFFFFFFFA, 1)


def observe(machine, pc, size, data):
    global ipc_control
    if 0x807F0100 <= pc < 0x807F0120:
        return
    if args.external_irq and external_boundary and pc == 0x80217C24:
        uc.emu_stop()
        return
    if args.exception_vector and 0x500 <= pc < 0x598:
        return
    if pc in (0x807F4000, 0x807F6000, 0x807F7000):
        uc.emu_stop()
        return
    if args.external_irq and pc == 0x8021C000:
        uc.reg_write(regs[3], 1)
        uc.reg_write(regs[4], 0x23456789)
        events.extend([42, 1, 0x23456789, 0])
        uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
        return
    if args.external_irq and pc == 0x80241F00 and uc.reg_read(ppc.UC_PPC_REG_LR) == 0x80217C24:
        assert uc.reg_read(regs[3]) == 27 and uc.reg_read(regs[4]) == 0x80680000 and load(0x8052AB00) == 1
        events.extend([40, 27, 0x80680000, 1])
    if args.reply_handler and pc in ((0x80212FA0, 0x80243C00) if args.ipc_registers else (0x80241C20, 0x80241C30, 0x80212FA0, 0x80243C00)) or args.ipc_ack and pc == 0x80243BF0 or args.transport and (pc in (0x80212FD0, 0x80243B60) or pc == 0x802438B0 and not args.open_lifecycle):
        a, b = uc.reg_read(regs[3]), uc.reg_read(regs[4])
        if pc == 0x80241C20:
            assert a in (1, 2)
            events.extend([13, a, 0, 0])
            uc.reg_write(regs[3], 0x006A0020 if a == 2 else ipc_control if args.ipc_interrupt else 0x30)
        else:
            kind = {0x80241C30: 12, 0x80212FA0: 20, 0x80243C00: 22, 0x80243BF0: 23, 0x80212FD0: 1, 0x80243B60: 11, 0x802438B0: 15}[pc]
            if kind == 12:
                allowed = (0x31, 0x34, 0x38, 0x14, 0x18) if args.ipc_interrupt else (0x31, 0x34, 0x38) if args.transport else (0x34, 0x38)
                if args.ipc_ack:
                    allowed += (0x22,)
                assert (a == 1 and b in allowed) or args.transport and (a, b) == (0, 0x006A0020)
                if args.ipc_interrupt and a == 1 and b in ((0x14, 0x18, 0x22) if args.ipc_ack else (0x14, 0x18)):
                    ipc_control = b
            if kind == 20:
                assert (a, b) == (0x806A0020, 32)
            if kind == 15:
                assert (a, b) == (0, 0x806A0020)
            events.extend([kind, a, b, 0])
        uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
        return
    if pc in (0x802174E0, 0x80217520) and not args.original_irqs:
        kind = 3 if pc == 0x802174E0 else 4
        events.extend([kind, 0 if kind == 3 else uc.reg_read(regs[3]), 0, 0])
        if kind == 3:
            uc.reg_write(regs[3], 0)
        uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
        return
    assert (0x80213830 <= pc < 0x802139F8 or 0x8021A790 <= pc < 0x8021A9BC
            or 0x8021B4E0 <= pc < 0x8021B6C8 or pc == 0x8021A1A0
            or args.deferred_wakeup and 0x8021A9C0 <= pc < 0x8021A9D4
            or args.reply_handler and 0x80241CA0 <= pc < 0x80241EF8
            or args.ipc_interrupt and 0x80241F00 <= pc < 0x802420AC
            or args.external_irq and (0x802179B0 <= pc < 0x80217CB0 or 0x8021A460 <= pc < 0x8021A49C or 0x8021A4A0 <= pc < 0x8021A4DC)
            or args.ipc_registers and 0x80241C20 <= pc < 0x80241C40
            or args.transport and (0x802421F0 <= pc < 0x80242430 or 0x8021A440 <= pc < 0x8021A450)
            or args.open_lifecycle and (0x80242550 <= pc < 0x80242674 or 0x80243570 <= pc < 0x80243A98)
            or args.original_irqs and (0x802174E0 <= pc < 0x802174F4 or 0x80217520 <= pc < 0x80217544)), hex(pc)


uc.hook_add(UC_HOOK_CODE, observe)
if args.reply_handler:
    def observe_mmio(machine, access, address, size, value, data):
        global ipc_control, ipc_message, ipc_arm_message, ipc_flags, reply_pending
        if args.exception_vector and 0x0C000000 <= address < 0x10000000:
            address |= 0xC0000000
        if args.ipc_registers and address in (0xCD000000, 0xCD000004):
            assert size == 4
            index = (address - 0xCD000000) // 4
            assert (index == 0 and value == 0x006A0020) or (index == 1 and value in ((0x31, 0x32, 0x34, 0x38) if args.ipc_control else (0x31, 0x14, 0x18, 0x22)))
            events.extend([12, index, value, 0])
            if args.ipc_control:
                if index == 0:
                    ipc_message = value
                elif value == 0x31:
                    assert ipc_message == 0x006A0020 and ipc_control == 0x30
                    ipc_control = value
                else:
                    ipc_control = (ipc_control & 6 & ~value) | (value & 0x38)
                    if args.ipc_irq and ((value & 4 and ipc_control & 0x10) or (value & 2 and ipc_control & 0x20)):
                        ipc_flags |= 0x40000000
            elif index == 1 and value in (0x14, 0x18, 0x22):
                ipc_control = value
            return
        if address >= 0xCD000000:
            assert (address, size, value) == (0xCD000030, 4, 0x40000000)
            if args.ipc_irq:
                ipc_flags = 0
                if reply_pending:
                    ipc_arm_message = ipc_message
                    ipc_control |= 4
                    reply_pending = False
            events.extend([16, 0x0D000030, value, 0])
    uc.hook_add(UC_HOOK_MEM_WRITE, observe_mmio)
    if args.ipc_registers:
        def observe_mmio_read(machine, access, address, size, value, data):
            if args.exception_vector and 0x0C000000 <= address < 0x10000000:
                address |= 0xC0000000
            if args.external_irq and address in (0xCC003000, 0xCC003004):
                assert size == 4
                selected = ipc_cause if address == 0xCC003000 else 0x4000
                store(address, selected)
                events.extend([41, address & 0x1FFFFFFF, selected, 0])
                return
            if address >= 0xCD000000:
                assert size == 4 and address in (0xCD000004, 0xCD000008)
                index = (address - 0xCD000000) // 4
                events.extend([13, index, 0, 0])
                store(address, (ipc_arm_message if args.ipc_control else 0x006A0020) if index == 2 else ipc_control)
        uc.hook_add(UC_HOOK_MEM_READ, observe_mmio_read)


def spr(number, value=None):
    saved = uc.reg_read(regs[31])
    if value is not None:
        uc.reg_write(regs[31], value)
    store(0x807F0100, (0x7FE002A6 if value is None else 0x7FE003A6) | (number & 31) << 16 | (number >> 5) << 11)
    uc.emu_start(0x807F0100, 0x807F0104, count=1)
    result = uc.reg_read(regs[31])
    uc.reg_write(regs[31], saved)
    return result


def compare(row):
    if args.ipc_control:
        uc.mem_write(0x806A1200, struct.pack('>6I', ipc_message, ipc_arm_message, ipc_control, 0, 0x40000000, 0))
        if args.ipc_irq:
            uc.mem_write(0x806A1218, struct.pack('>2I', ipc_flags, ipc_cause))
    state = [uc.reg_read(ppc.UC_PPC_REG_PC), uc.reg_read(ppc.UC_PPC_REG_LR), uc.reg_read(ppc.UC_PPC_REG_CTR),
             spr(1), uc.reg_read(ppc.UC_PPC_REG_CR), uc.reg_read(ppc.UC_PPC_REG_MSR)]
    state += [uc.reg_read(reg) for reg in regs]
    state += [spr(26), spr(27)] + [spr(i) for i in range(913, 920)]
    if args.exception_vector:
        state += [spr(i) for i in range(272, 276)]
    memory = b''.join(bytes(uc.mem_read(address, size)) for address, size in spans).hex()
    assert list(map(int, row[:-1])) == state + [len(events)] + events and row[-1] == memory, (case, state, row[:-1])
    return {'state': state, 'events': list(events), 'memoryHex': memory}


records = []
if args.exception_vector:
    for bank, first in (('ibat', 528), ('dbat', 536)):
        for index, pair in enumerate(bat_seed[bank][:4]):
            for half, value in enumerate(pair):
                spr(first + index * 2 + half, value)
    assert [spr(i) for i in (528, 529, 536, 537)] == bat_seed['ibat'][0] + bat_seed['dbat'][0]
for index, case in enumerate(cases):
    a_priority, b_priority, owner, msr, xer, flags = case
    for address, size in spans:
        if args.heap_reuse and index and address in (0x806A0000, 0x804B2B40):
            continue
        uc.mem_write(address, bytes(size))
    if args.external_irq:
        for i, value in enumerate(priority_words):
            store(0x8042CF98 + i * 4, value)
        store(0x8052AAD8, 0x80003040)
        store(0x800030AC, 0x80241F00)
    if args.exception_vector:
        vector = bytearray(struct.pack('>38I', *vector_words))
        struct.pack_into('>I', vector, 0x68, 0x38600004)
        uc.mem_write(0x80000500, bytes(vector))
        uc.mem_write(0x500, bytes(vector))
        store(0x80003010, 0x80217C60)
        for i in range(272, 276):
            spr(i, 0)
    if args.open_lifecycle and (not args.heap_reuse or index == 0):
        for i, value in [(1, 0x80700000), (3, 0x806A0000), (4, 64 if args.allocation_failure else 4096), (13, 0x8052E720)]:
            uc.reg_write(regs[i], value)
        for reg, value in [(ppc.UC_PPC_REG_LR, 0x807F9000), (ppc.UC_PPC_REG_MSR, 0), (ppc.UC_PPC_REG_CR, 0)]:
            uc.reg_write(reg, value)
        spr(1, 0)
        uc.emu_start(0x80243570, 0x807F9000, count=2000)
        assert uc.reg_read(regs[3]) == 0
        uc.mem_write(0x806FFF80, bytes(160))
    if args.transport:
        store(0x80528B70, 1)
    if args.kernel_reply:
        uc.mem_write(0x806A1000, b'/dev/openshsm_missing\x00'.ljust(64, b'\x00'))
        if not args.open_lifecycle:
            store(0x806A0020, 1)
            store(0x806A002C, 0x006A1000)
            store(0x806A0030, 1)
    for i, register in enumerate(regs):
        uc.reg_write(register, 0x12340000 + i)
        store(0x80680000 + i * 4, 0x56780000 + i)
    for offset, value in [(4, 0x806FF000), (12, 1), (52, 0x8052E720), (0x80, 0x87654321),
                          (0x84, 0x807F5000), (0x88, 0x13570000), (0x8C, xer), (0x198, 0x807F4000),
                          (0x19C, msr), (0x2D0, b_priority), (0x2DC, 0x80492970 + b_priority * 8)]:
        store(0x80680000 + offset, value)
    for i in range(1, 8):
        store(0x806801A4 + i * 4, i)
    for address, value in [(0x806801A2, flags), (0x806802C8, 1), (0x806902C8, 2)]:
        uc.mem_write(address, struct.pack('>H', value))
    for address, value in [(0x806902D0, a_priority), (0x80492970 + b_priority * 8, 0x80680000),
                           (0x80492974 + b_priority * 8, 0x80680000), (0x8052AB08, 1 << (31 - b_priority)),
                           (0x80528A30, 0x8021A1A0), (0x800000D4, 0x80690000), (0x800000E4, 0x80690000),
                           (0x800000D8, [0, 0x80690000, 0x80680000][owner])]:
        store(address, value)
    for i, value in [(1, 0x80700000), (3, 0x806A004C), (13, 0x8052E720)]:
        uc.reg_write(regs[i], value)
    for reg, value in [(ppc.UC_PPC_REG_LR, 0x807F0000), (ppc.UC_PPC_REG_CTR, 0),
                        (ppc.UC_PPC_REG_CR, 0), (ppc.UC_PPC_REG_MSR, msr)]:
        uc.reg_write(reg, value)
    for number, value in [(1, xer), (26, 0), (27, 0), *[(i, 0) for i in range(913, 920)]]:
        spr(number, value)
    events.clear()
    ipc_control = 0x30
    ipc_message = ipc_arm_message = 0
    ipc_flags, ipc_cause, reply_pending = 0, 0x10000, False
    if args.transport:
        uc.reg_write(regs[3], 0x806A1000 if args.open_lifecycle else 0x806A0020)
        uc.reg_write(regs[4], 1 if args.open_lifecycle else 0)
    uc.emu_start(0x80242550 if args.open_lifecycle else 0x802421F0 if args.transport else 0x8021B4E0, 0x807F0000, count=5000)
    sleeping = compare(rows[index * phase_count])
    if args.allocation_failure:
        assert sleeping['state'][0] == 0x807F0000 and sleeping['state'][9] == 0xFFFFFFEA
        assert not events and load(0x804B2B44) == 0 and load(0x804B2B4C) == 0x806A0000
        assert load(0x806A0004) == 48 and load(0x804B2A84) == 0 and load(0x80528B70) == 1
        assert load(0x800000E4) == load(0x800000D4) == 0x80690000
        assert bytes(uc.mem_read(0x806902C8, 2)) == b'\x00\x02'
        assert sleeping['state'][5] & 0x8000 == msr & 0x8000
        records.append({'input': case, 'failure': sleeping})
        continue
    request_initial_result = load(0x806A0024) if args.open_lifecycle else None
    assert sleeping['state'][0] == 0x807F4000 and load(0x800000E4) == load(0x800000D4) == 0x80680000
    assert load(0x806A004C) == load(0x806A0050) == 0x80690000
    assert bytes(uc.mem_read(0x806902C8, 2)) == b'\x00\x04' and load(0x80690198) == 0x8021A890
    if args.transport:
        assert [events[i] for i in range(0, len(events), 4)] == ([1] if args.open_lifecycle else []) + [1, 11, 12, 13, 12]
        assert load(0x804B2A80) == load(0x804B2A84) == 1 and load(0x80528B70) == 0
    else:
        assert sleeping['events'] == ([] if args.original_irqs else [3, 0, 0, 0])
    if args.original_irqs:
        assert load(0x8069019C) == msr & ~0x8000
    uc.reg_write(regs[3], 0x806A004C)
    uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F6000)
    if args.deferred_wakeup:
        store(0x800000D4, 0x806B0000)
        uc.reg_write(ppc.UC_PPC_REG_MSR, uc.reg_read(ppc.UC_PPC_REG_MSR) & ~0x8000)
    acked = None
    if args.ipc_irq:
        uc.mem_write(0x806A0020, reply_header)
        events.extend([14, 0xFFFFFFFA, 0x006A0020, 0])
        reply_pending = True
        ipc_flags, ipc_cause = 0x40000000, 0x14000
    if args.ipc_ack:
        heap_before_ack = bytes(uc.mem_read(0x806A0000, 4096))
        uc.reg_write(regs[3], 0)
        uc.reg_write(regs[4], 0x806B0000)
        ipc_control = (ipc_control & ~1) | 2 if args.ipc_control else 0x22
        uc.emu_start(0x80241F00, 0x807F0000, count=3000)
        acked = compare(rows[index * phase_count + 1])
        assert acked['state'][0] == 0x807F6000 and load(0x80528B70) == 1
        assert bytes(uc.mem_read(0x806902C8, 2)) == b'\x00\x04' and load(0x806A0020) == (8 if args.ipc_irq else 1)
        before_bytes = bytes.fromhex(sleeping['memoryHex'])
        ack_bytes = bytes.fromhex(acked['memoryHex'])
        assert ack_bytes[2048:6144] == heap_before_ack
        table_offset = sum(size for address, size in spans[:next(i for i, (address, size) in enumerate(spans) if address == 0x804B2B40)])
        assert ack_bytes[table_offset:table_offset + 128] == before_bytes[table_offset:table_offset + 128]
        assert ipc_control == (0x34 if args.ipc_irq else 0x30 if args.ipc_control else 0x22)
        assert [events[i] for i in range(0, len(events), 4)][-6:] == [13, 13, 13, 12, 16, 23]
        uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F6000)
    if args.reply_handler:
        if args.kernel_reply and not args.ipc_irq:
            uc.mem_write(0x806A0020, reply_header)
            events.extend([14, 0xFFFFFFFA, 0x006A0020, 0])
        elif not args.ipc_irq:
            store(0x806A0020, 8)
            store(0x806A0024, 0xFFFFFFFA)
            store(0x806A0028, 1)
        if not args.external_irq:
            uc.reg_write(regs[3], 0)
            uc.reg_write(regs[4], 0x806B0000)
    if args.ipc_interrupt:
        if args.ipc_irq:
            assert not reply_pending and ipc_flags == 0 and ipc_cause == 0x14000
            ipc_flags = 0x40000000
            events.extend([24, ipc_cause, ipc_flags, ipc_control])
        elif args.ipc_control:
            ipc_arm_message = ipc_message
            ipc_control |= 4
        else:
            ipc_control = 0x14
    if args.external_irq:
        base = 0x80680000
        if args.exception_vector:
            store(0x800000D4, base)
            store(0x800000C0, base & 0x3FFFFFFF)
            saved_msr = uc.reg_read(ppc.UC_PPC_REG_MSR)
            spr(26, 0x807F4000)
            spr(27, saved_msr | 2)
            uc.reg_write(ppc.UC_PPC_REG_MSR, saved_msr & ~0x8032)
        else:
            for i in range(3, 6):
                store(base + i * 4, uc.reg_read(regs[i]))
            for offset, value in [(0x80, uc.reg_read(ppc.UC_PPC_REG_CR)), (0x84, uc.reg_read(ppc.UC_PPC_REG_LR)),
                                  (0x88, uc.reg_read(ppc.UC_PPC_REG_CTR)), (0x8C, spr(1)),
                                  (0x198, 0x807F4000), (0x19C, uc.reg_read(ppc.UC_PPC_REG_MSR))]:
                store(base + offset, value)
            uc.mem_write(base + 0x1A2, struct.pack('>H', 2))
            store(0x800000D4, base)
            store(0x800000C0, base & 0x3FFFFFFF)
            uc.reg_write(regs[3], 4)
            uc.reg_write(regs[4], base)
        external_boundary = True
        try:
            uc.emu_start(0x500 if args.exception_vector else 0x80217C60, 0x807F0000, count=5000)
        except Exception as error:
            pc = uc.reg_read(ppc.UC_PPC_REG_PC)
            failed_msr = uc.reg_read(ppc.UC_PPC_REG_MSR)
            if args.exception_vector:
                uc.reg_write(ppc.UC_PPC_REG_MSR, failed_msr & ~0x30)
                bat = {str(number): hex(spr(number)) for number in (528, 529, 536, 537)}
                uc.reg_write(ppc.UC_PPC_REG_MSR, failed_msr)
                (output / 'vector-oracle-gap.json').write_text(json.dumps({'result': 'VECTOR_ORACLE_MM_TRANSLATION_UNVERIFIED', 'input': case, 'pc': hex(pc), 'msr': hex(failed_msr), 'ibat0Dbat0': bat,
                    'limits': ['Native execution is not differential acceptance; complete the oracle BAT/physical-memory setup before claiming equivalence.']}, indent=2) + '\n')
            raise RuntimeError(f'Vector oracle input={case}, PC={pc:#x}, MSR={failed_msr:#x}') from error
        external_boundary = False
    else:
        uc.emu_start(0x80241F00 if args.ipc_interrupt else 0x80241CA0 if args.reply_handler else 0x8021B5D0, 0x807F0000, count=3000)
    if args.ipc_irq:
        assert ipc_flags == 0 and ipc_control == 0x38
        if not args.external_irq:
            ipc_cause = 0x10000
    ready = None
    if args.deferred_wakeup:
        ready = compare(rows[index * phase_count + (2 if args.ipc_ack else 1)])
        assert ready['state'][0] == (0x80217C24 if args.external_irq else 0x807F6000)
        assert load(0x800000D4) == (0x80680000 if args.external_irq else 0x806B0000) and load(0x800000E4) == 0x80680000
        if args.external_irq:
            assert load(0x8052AB00) == 1
        if args.exception_vector:
            assert ready['state'][47] == acked['state'][10]
            assert load(0x80680010) == acked['state'][10]
            assert load(0x8068019C) == acked['state'][5] | 2
        assert bytes(uc.mem_read(0x806902C8, 2)) == b'\x00\x01'
        assert load(0x8052AB08) == 1 << (31 - a_priority) and load(0x8052AB04) == 1
        if args.reply_handler:
            assert load(0x806A0024) == 0xFFFFFFFA and load(0x806A004C) == load(0x806A0050) == 0
            assert [events[i] for i in range(0, len(events), 4)] == ([1] if args.open_lifecycle else []) + ([1, 11, 12, 13, 12] if args.transport else []) + ([14] if args.ipc_irq else []) + ([13, 13, 13, 12, 16, 23] if args.ipc_ack else []) + ([14] if args.kernel_reply and not args.ipc_irq else []) + ([24] if args.ipc_irq else []) + ([41, 41, 42, 40] if args.external_irq else []) + ([13] if args.ipc_interrupt else []) + [13, 13, 12, 16, 20, 13, 12, 22] + ([13] if args.ipc_interrupt else [])
            if args.ipc_interrupt:
                assert ipc_control == (0x38 if args.ipc_control else 0x18)
        if args.external_irq:
            ipc_cause = 0x10000
            uc.emu_start(0x80217C24, 0x807F0000, count=5000)
            assert load(0x8052AB00) == 0
        else:
            uc.reg_write(regs[3], 0x80680000)
            uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F7000)
            uc.emu_start(0x80213830, 0x807F0000, count=100)
            assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x807F7000
            uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F8000)
            uc.emu_start(0x8021A9C0, 0x807F0000, count=3000)
    resumed = compare(rows[index * phase_count + (3 if args.vector_return else phase_count - 1)])
    assert resumed['state'][0] == 0x807F0000 and resumed['state'][7] == 0x80700000
    assert load(0x800000E4) == load(0x800000D4) == 0x80690000
    assert load(0x806A004C) == load(0x806A0050) == 0
    assert bytes(uc.mem_read(0x806902C8, 2)) == b'\x00\x02' and load(0x806902DC) == 0
    assert load(0x80492970 + b_priority * 8) == load(0x80492974 + b_priority * 8) == 0x80680000
    assert load(0x8052AB08) == 1 << (31 - b_priority)
    if not args.reply_handler:
        assert resumed['events'] == ([] if args.original_irqs else [3, 0, 0, 0, 3, 0, 0, 0, 4, 0, 0, 0])
    if args.original_irqs:
        assert resumed['state'][5] & 0x8000 == msr & 0x8000
    if args.transport:
        assert resumed['state'][9] == 0xFFFFFFFA
        if args.open_lifecycle:
            assert load(0x804B2B44) == 0 and load(0x804B2B4C) == 0x806A0000 and load(0x806A0004) == 4080
        else:
            assert [events[i] for i in range(0, len(events), 4)][-1] == 15
    restored_b = None
    if args.vector_return:
        uc.reg_write(regs[3], 0x806A1300)
        uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F9000)
        uc.emu_start(0x8021A440, 0x807F9000, count=100)
        assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x807F9000
        uc.reg_write(regs[3], 0x806A1300)
        uc.reg_write(ppc.UC_PPC_REG_LR, 0x807FA000)
        uc.emu_start(0x8021B4E0, 0x807F0000, count=3000)
        restored_b = compare(rows[index * phase_count + 4])
        assert restored_b['state'][0] == 0x807F4000
        assert restored_b['state'][1:5] == acked['state'][1:5]
        assert restored_b['state'][6:38] == acked['state'][6:38]
        assert restored_b['state'][5] == acked['state'][5] | 2
        assert restored_b['state'][38:40] == [0x807F4000, acked['state'][5] | 2]
        assert restored_b['state'][40:47] == acked['state'][40:47]
        assert load(0x800000D4) == load(0x800000E4) == 0x80680000
        assert bytes(uc.mem_read(0x806902C8, 2)) == b'\x00\x04'
        assert bytes(uc.mem_read(0x806802C8, 2)) == b'\x00\x02'
        assert load(0x806A1300) == load(0x806A1304) == 0x80690000
        assert not int.from_bytes(uc.mem_read(0x806801A2, 2), 'big') & 2
    records.append({'input': case, 'requestInitialResult': request_initial_result, 'sleeping': sleeping, 'acked': acked, 'ready': ready, 'resumed': resumed, 'restoredB': restored_b})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'ORIGINAL_SLEEP_SELECTOR_WAKEUP_RESUME72_CASES_PASS', 'cases': len(cases), 'records': records,
          'hostSha256': sha(host), 'selectorHostSha256': sha(Path('experiments/wii-static-recomp/ios_select_thread_host.cpp')),
          'includedHostSha256': sha(Path('experiments/wii-static-recomp/ios_open_host.cpp')), 'scriptSha256': sha(Path(__file__)),
          'dolSha256': sha(dol_path), 'sources': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
          'memorySliceBytesPerPhase': sum(size for address, size in spans),
          'analyses': {str(path.parent / 'analysis.json'): sha(path.parent / 'analysis.json') for path in analysis_sources},
          'limits': ['Prepared two-thread contexts, priorities A<B, current D4/E4 equal, saved EE0.',
                     'Host invokes wakeup at prepared B entry; native bounded dispatch handles original callback and resumed PCs.',
                     'Interrupt disable/restore remain explicit fixtures; no EE1/IRQ/FPU lifecycle/idle/transport or full boot.',
                     'Independent PPC750CL execution, not a physical Wii trace; B wakeup caller remains suspended at endpoint.']}
if args.original_irqs:
    report['result'] = 'ORIGINAL_THREAD_CYCLE_IRQ_PRIMITIVES144_CASES_PASS'
    report['irqCompareSoChanges'] = irq_changes
    report['pendingInterruptRefusalVerified'] = True
    report['limits'] = ['Original disable/restore now execute; initial EE0/1 tested without pending IRQ producers.',
                        'Native callback adapter permits only empty event state and rejects pending IRQ; no real interrupt delivery.',
                        'Prepared B context/entry and host wakeup; no FPU lifecycle/idle/IOS-completion or full boot.',
                        'Independent PPC750CL, not physical Wii; B wakeup caller remains suspended at endpoint.']
if args.deferred_wakeup:
    report['result'] = 'ORIGINAL_DEFERRED_WAKEUP_RESCHEDULE144_CASES_PASS'
    report['rescheduleCarryChanges'] = carry_changes
    report['limits'] = ['Prepared IRQ-context pointer D4 differs from running-thread E4; host clears EE to represent IRQ entry.',
                        'Original wakeup returns without switch; host calls original context setter and original reschedule, then A resumes.',
                        'NWii reschedule body inlines the selector; 144markers verified against DOL and scoped SO/carry corrections applied.',
                        'No actual IRQ vector/handler/IOS-completion/timing/FPU/idle/full boot; empty-event poll only.']
if args.reply_handler:
    report['result'] = 'ORIGINAL_REPLY_HANDLER_DEFERRED_WAKEUP_RESUME144_CASES_PASS'
    report['limits'] = ['Original reply handler calls original wakeup/selector under prepared D4/E4 mismatch; it completes ACK/profiler before reschedule.',
                        'Reply header is supplied (OPEN -6), not computed by IOSKernel; register/cache/profiler/MMIOclear are explicit fixtures.',
                        'Host restores current context and calls original reschedule; no actual IRQ vector/interrupted-state restoration.',
                        'No kernel/transport completion, FPU/idle/general memory coherence/full boot; empty-event poll only.']
if args.kernel_reply:
    report['result'] = 'ORIGINAL_THREAD_KERNEL_REPLY_HANDLER_RESUME144_CASES_PASS'
    report['kernelSourceHashes'] = {str(path): sha(path) for path in kernel_sources}
    report['packetAdapterSha256'] = sha(Path('experiments/wii-static-recomp/ipc_open_packet.h'))
    report['replyOracleSha256'] = sha(oracle_path)
    report['limits'] = ['Actual IOSKernel/private missing-device correction and EventScheduler tick1 form OPEN reply on shared MMU.',
                        'Reference imports retained original Dolphin reply header, preserving the original sleep-created wait queue.',
                        'Original reply handler/wakeup/selector/deferred reschedule/A resumption execute; IRQ-context entry/exit and B call site are PC adaptations.',
                        'No original transport/sender, real IRQ delivery/timing, full interrupted-state restoration, cache/FPU/idle/full boot.']
if args.transport and not args.allocation_failure:
    report['result'] = 'ORIGINAL_TRANSPORT_SLEEP_KERNEL_HANDLER_THREAD_RESUME144_CASES_PASS'
    report['limits'] = ['Original transport initializes wait queue, sends request, blocks via actual sleep/select/save/load, resumes and returns computed kernel result-6.',
                        'Register0 write arms actual EventScheduler reply; host advances tick1 at prepared B/IRQ entry, then original handler/deferred reschedule restores A.',
                        'Cache/profiler/MMIO/registers and free remain fixtures; request packet is prepared rather than original IOS_Open allocation.',
                        'No actual IRQ vector/delivery/timing/full interrupted-state restoration/cache visibility/heap cleanup/FPU/idle/MEM2/async/full boot.']
    mutant = subprocess.run([sys.executable, __file__, '--vector-return' if args.vector_return else '--exception-vector' if args.exception_vector else '--external-irq' if args.external_irq else '--ipc-irq' if args.ipc_irq else '--ipc-control' if args.ipc_control else '--ipc-registers' if args.ipc_registers else '--ipc-ack' if args.ipc_ack else '--ipc-interrupt' if args.ipc_interrupt else '--heap-reuse' if args.heap_reuse else '--open-lifecycle' if args.open_lifecycle else '--transport', '--drop-event-mutant'],
                            capture_output=True, text=True, timeout=180)
    (output / 'drop-event-mutant.log').write_text(mutant.stdout + mutant.stderr)
    assert mutant.returncode == 9 and 'THREAD_TRANSPORT_LOST_REPLY_DETECTED' in mutant.stdout, mutant.stderr[-2000:]
    report['lostReplyMutantDetected'] = True
if args.open_lifecycle:
    report['result'] = 'ORIGINAL_IOS_OPEN_ALLOCATE_TRANSPORT_COMPLETE_FREE144_CASES_PASS'
    report['openInstructionMarkers'] = len(open_markers)
    report['openCompareSoChanges'] = open_so_changes
    report['openCarryChanges'] = open_carry_changes
    report['limits'] = ['Original IOS_Open/heap creation/aligned allocation/transport/free execute; one call per fresh zeroed MEM1 heap.',
                        'Actual kernel/event reply and original handler/deferred reschedule restore A; final heap coalesces with allocation count0.',
                        'Cache/register/MMIO/profiler and IRQ entry/exit/timing/B-context remain adaptations.',
                        'No reused heap in this coupled test, fragmentation/invalid pointers/MEM2/async/FPU/idle/full IRQ/full boot.']
if args.heap_reuse:
    report['result'] = 'ORIGINAL_IOS_OPEN_SHARED_HEAP144_CYCLES_PASS'
    report['heapCreations'] = 1
    report['completedOpenCalls'] = len(cases)
    report['requestInitialResults'] = sorted({record['requestInitialResult'] for record in records})
    assert records[0]['requestInitialResult'] == 0 and all(record['requestInitialResult'] == 0xFFFFFFFA for record in records[1:])
    reused_mutant = subprocess.run([sys.executable, __file__, '--heap-reuse', '--drop-event-mutant', '--drop-after-reuse'],
                                   capture_output=True, text=True, timeout=180)
    (output / 'drop-reused-event-mutant.log').write_text(reused_mutant.stdout + reused_mutant.stderr)
    assert reused_mutant.returncode == 9 and 'THREAD_TRANSPORT_LOST_REPLY_DETECTED' in reused_mutant.stdout, reused_mutant.stderr[-2000:]
    report['lostReusedReplyMutantDetected'] = True
    report['limits'] = ['One heap creation, persistent4096MEM1 heap/table across144 original allocate/transport/complete/free cycles.',
                        'Thread/context/ring/IRQ fixtures reset between calls; only heap/table lifetime persists.',
                        'Reused request result may retain earlier completion; original sleep and new sender event remain required.',
                        'Lost-event mutants test fresh allocation and second reused request retaining-6; no fragmented/invalid/MEM2/async/full IRQ/cache/FPU/idle/full boot.']
if args.allocation_failure:
    report['result'] = 'ORIGINAL_IOS_OPEN_ALLOCATION_FAILURE144_CASES_PASS'
    report['heapSize'] = 64
    report['limits'] = ['Original64-byte heap cannot allocate64-byte/32-aligned request; original IOS_Open returns-22.',
                        'No request send/cache/profiler/free events; allocation count0/freehead/payload48 and current thread unchanged.',
                        'Native advances EventScheduler to1 after return and verifies no completion; prepared fixtures, not general rollback/full boot.']
if args.ipc_interrupt:
    report['result'] = 'ORIGINAL_IPC_INTERRUPT_OPEN_REPLY_THREAD_RESUME144_CASES_PASS'
    report['ipcControlAfterReply'] = ipc_control
    report['limits'] = ['Original IPCInterruptHandler reply gate/body executes around original reply handler, wakeup and deferred thread resumption.',
                        'Control14/18 and MMIO/cache/profiler are strict fixtures; ACK branch is outside scope and rejects execution.',
                        'Native kernel computes OPEN reply; reference uses retained Dolphin header with original PPC body execution.',
                        'Host prepares IRQ context/EE and invokes original context setter/reschedule; no real IRQ vector/entry/exit/timing/full boot.']
if args.ipc_ack:
    report['result'] = 'ORIGINAL_IPC_ACK_THEN_REPLY_OPEN_THREAD_RESUME144_CASES_PASS'
    ack_mutant = subprocess.run([sys.executable, __file__, '--vector-return' if args.vector_return else '--exception-vector' if args.exception_vector else '--external-irq' if args.external_irq else '--ipc-irq' if args.ipc_irq else '--ipc-control' if args.ipc_control else '--ipc-registers' if args.ipc_registers else '--ipc-ack', '--drop-event-mutant', '--drop-after-ack'],
                               capture_output=True, text=True, timeout=180)
    (output / 'drop-after-ack-mutant.log').write_text(ack_mutant.stdout + ack_mutant.stderr)
    assert ack_mutant.returncode == 9 and 'THREAD_ACK_WITHOUT_REPLY_DETECTED' in ack_mutant.stdout, ack_mutant.stderr[-2000:]
    report['ackWithoutReplyMutantDetected'] = True
    report['limits'] = ['Original ACK branch restores mailbox availability on an empty response ring before the reply branch.',
                        'ACK alone preserves waiting A/command1/full heap and descriptor table; only subsequent reply releases A and permits original free.',
                        'Control22 then14/18, zero timeout globals, MMIO/cache/profiler and IRQ entry/exit/timing remain PC fixtures.',
                        'Independent original PPC execution with retained Dolphin reply header; no queued-send/timeout/real vector/full boot acceptance.']
if args.ipc_registers:
    report['result'] = 'ORIGINAL_IPC_REGISTER_HELPERS_ACK_REPLY_OPEN_THREAD144_CASES_PASS'
    report['originalRegisterInstructions'] = 8
    report['limits'] = ['Original IPCReadReg/IPCWriteReg execute through MMU/MMIO with original r0/r3 effects; eight DOL words checked.',
                        'MMIO hook reuses existing strict register fixture, not the vendor hardware backend.',
                        'Original ACK/reply/Open/thread/free chain and both missing-event mutants checked; control/timing/cache/profiler/IRQ setup remain adaptations.',
                        'Vendor synchronous request dispatch and no-context synthetic success are not enabled; no full boot/real IRQ acceptance.']
if args.ipc_control:
    report['result'] = 'ORIGINAL_OPEN_THREAD_COUPLED_MEASURED_IPC_CONTROL144_CASES_PASS'
    report['controlBackendSha256'] = sha(Path('experiments/wii-static-recomp/ipc_reset_backend.cpp'))
    report['vendorIpcSha256'] = sha(upstream / 'src/hw/hw_ipc.cpp')
    report['controlOracleSha256'] = sha(private / 'dolphin-ipc-control/comparison.json')
    report['limits'] = ['Original register helpers call measured W1C/X2 projection on existing vendor IPC storage.',
                        'Original send control31 arms EventScheduler; message-register write alone no longer arms completion.',
                        'Host producer clears X1/raises ACK and reply at tick1; native kernel computes OPEN reply, reference imports retained Dolphin header.',
                        '24-byte backend snapshot joins four-phase memory comparison; IRQFLAG/PI cause/cache/timing/vector delivery remain fixtures/unverified.']
if args.ipc_irq:
    report['result'] = 'ORIGINAL_OPEN_THREAD_PREPARED_REPLY_LATCHED_IRQ144_CASES_PASS'
    report['irqOracleSha256'] = sha(private / 'dolphin-ipc-irq/comparison.json')
    report['irqBackendProofSha256'] = sha(private / 'ipc-irq-backend/comparison.json')
    report['limits'] = ['Native kernel prepares header8/-6 before ACK; original ACK wrapper leaves A waiting despite completed header.',
                        'Original IRQFLAG clear releases queued reply in host adapter; existing scheduler updates PI then dispatches original reply wrapper.',
                        '32backend snapshot bytes join four-phase comparison; lost-reply mutant retains prepared header8/-6 and active reply IRQ but cannot release A.',
                        'IRQ entry/exit/vector dispatch/producer/ticks/cache remain PC adaptations; independent PPC/model plus retained Dolphin observations, not full original boot.']
if args.external_irq:
    report['result'] = 'ORIGINAL_EXTERNAL_DISPATCH_IPC_OPEN_THREAD_RESUME144_CASES_PASS'
    report['priorityTableSha256'] = hashlib.sha256(struct.pack('>12I', *priority_words)).hexdigest()
    report['limits'] = ['Original dispatcher selects IPCInterruptHandler with IRQ27/B context, holds scheduler counter1 during original synchronous wakeup, then enables and reschedules into saved A.',
                        'Original IOS_Open/allocate/transport/sleep/ACK/reply/wakeup/free execute; no host-directed context setter/reschedule after the reply.',
                        'ACK entry, generic-vector preamble, B context, time service, queue producer/ticks/cache/profiler remain PC adaptations.',
                        'B dispatcher continuation remains suspended; no complete exception vector/EE1/FPU/full boot or physical-Wii equivalence claim.']
if args.exception_vector:
    report['result'] = f'ORIGINAL_EXCEPTION_VECTOR_DISPATCH_IPC_OPEN_RESUME{len(cases)}_CASES_PASS'
    report['initialTranslationMasks'] = sorted({case[3] & 0x30 for case in cases})
    report['vectorAnalysisSha256'] = sha(private / 'ios-exception-vector/analysis.json')
    report['loaderBatSeedSha256'] = sha(bat_seed_path)
    report['limits'] = ['Original38-instruction vector saves preamble/SPRG0 and routes external IRQ before original dispatcher/IPC/wakeup/scheduler/Open/free.',
                        'Reference executes copied152bytes at physical500; native uses original-address compiled labels with guarded ID4 read from copied instruction.',
                        'Prepared vector copy/ID4/table/C0/D4/B and hardware SRR0/SRR1/RI1/exception MSR remain adapters; no automatic hardware exception delivery.',
                        'Oracle uses measured Dolphin loader BAT0–3 with shared physical/virtual MEM1 and MMIO backing; no MEM2/HID4/extended-BAT or physical-Wii startup claim.',
                        'Clock/ACK/queue producer/ticks/cache/profiler remain fixtures; B continuation suspended, no full boot/gameplay/FPU or physical-Wii trace claim.']
if args.vector_return:
    report['result'] = f'ORIGINAL_VECTOR_IPC_OPEN_AND_INTERRUPTED_B_RESTORED{len(cases)}_CASES_PASS'
    report['limits'] = ['Original vector/dispatcher/IPC/thread/Open/free plus second original A sleep and B context-load/RFI execute; five phases compared.',
                        'B returns to saved interrupted endpoint807F4000 with original GPR/CR/XER/LR/CTR/GQR and supplied recoverable MSR, exception flag2 cleared.',
                        'Prepared second waitqueue/callsite, original vector copy/ID/table/hardware SRR entry and measured-loader BAT setup remain adapters.',
                        'Clock/ACK/queue producer/ticks/cache/profiler/MEM2/FPU/automatic exception delivery/full boot/gameplay remain unverified.']
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
stage = 'vector→IPC→Open→A sleep→B restored' if args.vector_return else 'IOS_Open allocation refusal' if args.allocation_failure else 'sleep→select→wakeup→resume'
print(f'PASS original {stage}: {len(cases)} cases; real IRQ delivery/full boot unverified')
