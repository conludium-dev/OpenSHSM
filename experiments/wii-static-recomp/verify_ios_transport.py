"""Execute original transport through queue/register fixtures and stop before unresolved sleep/free."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import struct
import subprocess
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--kernel-completion', action='store_true')
parser.add_argument('--drop-reply-mutant', action='store_true')
parser.add_argument('--reply-handler', action='store_true')
parser.add_argument('--handler-completion', action='store_true')
parser.add_argument('--drop-wakeup-mutant', action='store_true')
parser.add_argument('--wakeup-completion', action='store_true')
args = parser.parse_args()
args.handler_completion |= args.wakeup_completion
args.kernel_completion |= args.handler_completion

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import ppc_const as ppc
output = Path('work/private-game/static-recomp/ios-transport')
base_output = output
if args.reply_handler:
    assert not args.kernel_completion and not args.drop_reply_mutant
    output = base_output = Path('work/private-game/static-recomp/ios-reply-handler')
    output.mkdir(exist_ok=True)
if args.kernel_completion:
    output = Path('work/private-game/static-recomp/ios-wakeup-completion' if args.wakeup_completion else
                  'work/private-game/static-recomp/ios-handler-completion' if args.handler_completion else
                  'work/private-game/static-recomp/ios-transport-completion')
    output.mkdir(exist_ok=True)
if args.drop_reply_mutant:
    assert args.kernel_completion
    output = output / 'drop-reply-mutant'
    output.mkdir(exist_ok=True)
if args.drop_wakeup_mutant:
    assert args.handler_completion
    output = output / 'drop-wakeup-mutant'
    output.mkdir(exist_ok=True)
old_log = output / 'native.log'
if old_log.exists() and not (output / 'initial-compare-so-native.log').exists():
    (output / 'initial-compare-so-native.log').write_text(old_log.read_text())
prepare = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--compare-so',
                          *(['--reply-handler'] if args.reply_handler else [])],
                         capture_output=True, text=True, timeout=180)
assert prepare.returncode == 0, prepare.stderr[-2000:]
reply_source = []
if args.handler_completion:
    prepare_reply = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--compare-so', '--reply-handler'],
                                   capture_output=True, text=True, timeout=180)
    assert prepare_reply.returncode == 0, prepare_reply.stderr[-2000:]
    reply_source = ['work/private-game/static-recomp/ios-reply-handler/selected.cpp']
wakeup_source = []
if args.wakeup_completion:
    prepared_wakeup = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--compare-so', '--wakeup'],
                                    capture_output=True, text=True, timeout=180)
    assert prepared_wakeup.returncode == 0, prepared_wakeup.stderr[-2000:]
    wakeup_source = ['work/private-game/static-recomp/ios-wakeup/selected.cpp']
    if args.drop_wakeup_mutant:
        body = Path(reply_source[0]).read_text()
        assert body.count('func_8021B5D0(ctx);') == 1
        mutant_source = output / 'reply-without-wakeup.cpp'
        mutant_source.write_text('#include "runtime/cpu_context.h"\nextern "C" void experiment_drop_wakeup(nwii::runtime::CPUContext&);\n' +
                                 body.replace('func_8021B5D0(ctx);', 'experiment_drop_wakeup(ctx);'))
        reply_source = [str(mutant_source)]
extra_sources = []
if args.kernel_completion:
    upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
    kernel = Path('work/private-game/static-recomp/ipc-kernel-fixed/ios_kernel.cpp')
    assert kernel.read_text() == (upstream / 'src/hle/ios_kernel.cpp').read_text().replace('    return IPC_ENOENT;', '    return -6;')
    extra_sources = [str(kernel), str(upstream / 'src/core/event_scheduler.cpp')]
host = Path('experiments/wii-static-recomp/ios_transport_host.cpp')
exe = output / 'transport-host'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/include')
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
                        '-DSHSM_ORIGINAL_TRANSPORT', '-DSHSM_ORIGINAL_ALLOCATOR', '-ffunction-sections',
                        '-Wl,-dead_strip', '-I', str(runtime), '-I', 'experiments/wii-static-recomp',
                        *(['-DSHSM_KERNEL_COMPLETION'] if args.kernel_completion else []),
                        *(['-DSHSM_DROP_REPLY_MUTANT'] if args.drop_reply_mutant else []),
                        *(['-DSHSM_REPLY_HANDLER'] if args.reply_handler else []),
                        *(['-DSHSM_HANDLER_COMPLETION'] if args.handler_completion else []),
                        *(['-DSHSM_DROP_WAKEUP_MUTANT'] if args.drop_wakeup_mutant else []),
                        *(['-DSHSM_WAKEUP_COMPLETION'] if args.wakeup_completion else []),
                        str(host), str(base_output / 'selected.cpp'), *reply_source, *wakeup_source, *extra_sources,
                        '-I', 'work/private-game/static-recomp/mass-current', '-o', str(exe)],
                       capture_output=True, text=True, timeout=180)
(output / 'host-build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-2000:]
cases = list(itertools.product([0, 1], [0, 1, 15, 16, 17], [0, 1], [0, 1], [0, 0x80000000]))
if args.reply_handler:
    cases = list(itertools.product([0, 1], [0, 1, 0xFFFFFFFF, 0xFFFFFFFA], [0, 0x30], [0], [0, 0x80000000]))
native = subprocess.run([str(exe.resolve())], input=''.join(' '.join(map(str, row)) + '\n' for row in cases),
                        capture_output=True, text=True, timeout=60)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0, native.stderr[-2000:]
handler_stacks = [row.split()[1] for row in native.stdout.splitlines() if row.startswith('HANDLER_STACK ')]
wakeup_memory = [row.split()[1] for row in native.stdout.splitlines() if row.startswith('WAKEUP_MEMORY ')]
rows = [row.split() for row in native.stdout.splitlines() if not row.startswith(('[IOS', 'HANDLER_STACK ', 'WAKEUP_MEMORY '))]
assert len(rows) == len(cases)
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
if args.reply_handler or args.handler_completion:
    uc.mem_map(0xCD000000, 4096)
for i in range(18):
    if header[36 + i]:
        uc.mem_write(header[18 + i], dol[header[i]:header[i] + header[36 + i]])
regs = [getattr(ppc, f'UC_PPC_REG_{i}') for i in range(32)]
events = []
boundary = False
queued = False
reply_bytes = bytes.fromhex(json.loads(Path('work/private-game/static-recomp/dolphin-ipc-packet/comparison.json').read_text())['observations'][0]['replyPacketHex'])
services = {0x8021A440: 10, 0x80212FD0: 1, 0x802174E0: 3, 0x80217520: 4,
            0x80243B60: 11, 0x80241C30: 12, 0x80241C20: 13}
if args.reply_handler or args.handler_completion:
    services.update({0x80212FA0: 20, 0x8021B5D0: 21, 0x80243C00: 22})
if args.wakeup_completion:
    del services[0x8021B5D0]
    services[0x8021A790] = 30
handler_active = False
saved_state = None
wakeup_ready = False
restore_target = None


def observe(machine, pc, size, data):
    global boundary, queued, handler_active, saved_state, wakeup_ready, restore_target
    if pc in (0x807F0100, 0x807F0104):
        if args.wakeup_completion and pc == 0x807F0104 and restore_target is not None:
            uc.reg_write(regs[31], saved_state[regs[31]])
            uc.reg_write(ppc.UC_PPC_REG_PC, restore_target)
            restore_target = None
        return
    if args.handler_completion and pc == 0x807F0200:
        if args.wakeup_completion:
            wakeup_ready = (struct.unpack('>H', uc.mem_read(0x806802C8, 2))[0] == 1 and
                            struct.unpack('>I', uc.mem_read(0x804929A8, 4))[0] == 0x80680000)
        assert handler_active and wakeup_ready
        for register, value in saved_state.items():
            uc.reg_write(register, value)
        if args.wakeup_completion:
            restore_target = saved_state[ppc.UC_PPC_REG_LR]
            uc.reg_write(regs[31], xer)
            uc.reg_write(ppc.UC_PPC_REG_PC, 0x807F0100)
        else:
            uc.reg_write(ppc.UC_PPC_REG_PC, saved_state[ppc.UC_PPC_REG_LR])
        handler_active = False
        return
    if pc in (0x8021B4E0, 0x802438B0):
        if args.wakeup_completion and pc == 0x8021B4E0:
            queue = uc.reg_read(regs[3])
            uc.mem_write(queue, struct.pack('>II', 0x80680000, 0x80680000))
            uc.mem_write(0x806802C8, struct.pack('>H', 4))
            for address, value in [(0x806802CC, 0), (0x806802D0, 7), (0x806802DC, queue)]:
                uc.mem_write(address, struct.pack('>I', value))
        if args.kernel_completion and pc == 0x802438B0:
            events.extend([15, uc.reg_read(regs[3]), uc.reg_read(regs[4]), 0])
            uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
            return
        if args.kernel_completion and queued:
            uc.mem_write(0x806A0020, reply_bytes[:12] if args.wakeup_completion else reply_bytes)
            events.extend([14, 0xFFFFFFFA, 0x6A0020, 0])
            queued = False
            if args.handler_completion:
                saved_state = {register: uc.reg_read(register) for register in regs + [ppc.UC_PPC_REG_CR, ppc.UC_PPC_REG_LR, ppc.UC_PPC_REG_CTR]}
                handler_active = True
                uc.reg_write(regs[3], 0)
                uc.reg_write(regs[4], 0)
                uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F0200)
                uc.reg_write(ppc.UC_PPC_REG_PC, 0x80241CA0)
                return
            uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
            return
        boundary = True
        uc.emu_stop()
        return
    if pc in services:
        kind = services[pc]
        r3, r4 = uc.reg_read(regs[3]), uc.reg_read(regs[4])
        events.extend([kind, 0 if kind == 3 else r3, r4 if kind in (1, 11, 12, 20, 22) else 0, 0])
        if args.kernel_completion and kind == 12 and r3 == 0:
            assert r4 == 0x6A0020
            queued = True
        if kind in (3, 13):
            value = 0 if kind == 3 else 0x30
            if (args.reply_handler or handler_active) and kind == 13:
                value = (0x6A0020 if present else 0) if r3 == 2 else (0x30 if handler_active else ack)
            uc.reg_write(regs[3], value)
        if handler_active and kind == 21:
            assert r3 == 0x806A004C
            wakeup_ready = True
        uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
        return
    allowed = (0x80241CA0 <= pc < 0x80241EF8) if args.reply_handler or handler_active else (0x802421F0 <= pc < 0x80242430)
    allowed |= args.wakeup_completion and 0x8021B5D0 <= pc < 0x8021B6C8
    assert allowed, hex(pc)


uc.hook_add(UC_HOOK_CODE, observe)
if args.reply_handler or args.handler_completion:
    def mmio_write(machine, access, address, size, value, data):
        assert address == 0xCD000030 and size == 4 and value == 0x40000000
        events.extend([16, 0x0D000030, value, 0])
    uc.hook_add(UC_HOOK_MEM_WRITE, mmio_write, begin=0xCD000000, end=0xCD000FFF)
spans = [(0x806A0020, 64), (0x804B2A80, 80), (0x806FFFC0, 96), (0x80528B70, 4)]
if args.reply_handler or args.handler_completion:
    assert len(handler_stacks) == len(cases)
    spans.append((0x806FFCE0, 832) if args.wakeup_completion else (0x806FFD00, 800))
if args.wakeup_completion:
    assert len(wakeup_memory) == len(cases)
    spans += [(0x80680000, 1024), (0x80492970, 256), (0x8052AB04, 8)]
records = []
for case, row in zip(cases, rows):
    present, pending, ack, asynchronous, xer = case
    for address, size in spans:
        uc.mem_write(address, bytes(size))
    for address, value in [(0x804B2A84, pending), (0x80528B70, ack), (0x80528B74, 0),
                           (0x806A0020, 1), (0x806A0024, 0xFFFFFFFA)]:
        uc.mem_write(address, struct.pack('>I', value))
    if args.reply_handler:
        uc.mem_write(0x806A0020, struct.pack('>III', 8, pending, 1))
    if args.kernel_completion:
        uc.mem_write(0x806A0024, bytes(4))
        uc.mem_write(0x806A002C, struct.pack('>II', 0x6A1000, 1))
    for i, register in enumerate(regs):
        uc.reg_write(register, 0x12340000 + i)
    for i, value in [(1, 0x80700000), (3, 0x806A0020 if present else 0), (4, asynchronous), (13, 0x8052E720)]:
        uc.reg_write(regs[i], value)
    for register, value in [(ppc.UC_PPC_REG_LR, 0x807F0000), (ppc.UC_PPC_REG_CTR, 0), (ppc.UC_PPC_REG_CR, 0)]:
        uc.reg_write(register, value)
    uc.mem_write(0x807F0100, struct.pack('>II', 0x7FE103A6, 0x7FE102A6))
    uc.reg_write(regs[31], xer)
    uc.emu_start(0x807F0100, 0x807F0104, count=1)
    uc.reg_write(regs[31], 0x1234001F)
    events.clear()
    boundary = False
    queued = False
    handler_active = False
    wakeup_ready = False
    restore_target = None
    uc.emu_start(0x80241CA0 if args.reply_handler else 0x802421F0, 0x807F0000, count=2000)
    pc, saved31 = uc.reg_read(ppc.UC_PPC_REG_PC), uc.reg_read(regs[31])
    uc.emu_start(0x807F0104, 0x807F0108, count=1)
    observed_xer = uc.reg_read(regs[31])
    uc.reg_write(regs[31], saved31)
    state = [int(boundary), pc, uc.reg_read(ppc.UC_PPC_REG_LR), uc.reg_read(ppc.UC_PPC_REG_CTR),
             observed_xer, uc.reg_read(ppc.UC_PPC_REG_CR)] + [uc.reg_read(reg) for reg in regs]
    expected = state + [len(events)] + events
    memory = b''.join(bytes(uc.mem_read(address, size)) for address, size in spans).hex()
    native_memory = row[-1] + (handler_stacks[len(records)] if args.reply_handler or args.handler_completion else '')
    if args.wakeup_completion:
        native_memory += wakeup_memory[len(records)]
    matches = list(map(int, row[:-1])) == expected and native_memory == memory
    if (args.drop_reply_mutant or args.drop_wakeup_mutant) and not matches:
        assert case == (1, 0, 1, 0, 0)
        print('MUTANT_LOST_WAKEUP_DETECTED' if args.drop_wakeup_mutant else 'MUTANT_LOST_REPLY_DETECTED')
        sys.exit(9)
    assert matches, (case, row[:-1], expected)
    records.append({'input': case, 'state': state, 'events': list(events), 'memoryHex': memory})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
completion_count = 0
if args.kernel_completion:
    for record in records:
        groups = [record['events'][i:i + 4] for i in range(0, len(record['events']), 4)]
        if any(group[0] == 14 for group in groups):
            completion_count += 1
            assert record['state'][0] == 0 and record['state'][1] == 0x807F0000
            assert record['state'][9] == 0xFFFFFFFA and record['memoryHex'][:128] == reply_bytes.hex()
    assert completion_count == 6
    if not args.drop_reply_mutant and not args.drop_wakeup_mutant:
        mutants = [('--drop-reply-mutant', 'MUTANT_LOST_REPLY_DETECTED')]
        if args.handler_completion:
            mutants.append(('--drop-wakeup-mutant', 'MUTANT_LOST_WAKEUP_DETECTED'))
        for flag, marker in mutants:
            mutant = subprocess.run([sys.executable, __file__, '--wakeup-completion' if args.wakeup_completion else '--handler-completion' if args.handler_completion else
                                     '--kernel-completion', flag], capture_output=True, text=True, timeout=180)
            (output / ('mutant-' + flag[2:] + '.log')).write_text(mutant.stdout + mutant.stderr)
            assert mutant.returncode == 9 and marker in mutant.stdout, mutant.stderr[-2000:]
    if args.handler_completion:
        for record in records:
            groups = [record['events'][i:i + 4] for i in range(0, len(record['events']), 4)]
            completed = any(group[0] == 14 for group in groups)
            if args.wakeup_completion:
                assert [group for group in groups if group[0] == 30] == ([[30, 0, 0, 0]] if completed else [])
                data = bytes.fromhex(record['memoryHex'])
                if completed:
                    thread = data[1076:2100]
                    ready = data[2100:2356]
                    globals_data = data[2356:2364]
                    assert struct.unpack_from('>H', thread, 0x2C8)[0] == 1
                    assert struct.unpack_from('>I', thread, 0x2DC)[0] == 0x804929A8
                    assert struct.unpack_from('>II', ready, 7 * 8) == (0x80680000, 0x80680000)
                    assert struct.unpack('>II', globals_data) == (1, 0x01000000)
            else:
                assert [group for group in groups if group[0] == 21] == ([[21, 0x806A004C, 0, 0]] if completed else [])
            assert [group for group in groups if group[0] == 20] == ([[20, 0x806A0020, 32, 0]] if completed else [])
if args.reply_handler:
    for record in records:
        groups = [record['events'][i:i + 4] for i in range(0, len(record['events']), 4)]
        present = record['input'][0]
        assert [group for group in groups if group[0] == 21] == ([[21, 0x806A004C, 0, 0]] if present else [])
        assert [group for group in groups if group[0] == 20] == ([[20, 0x806A0020, 32, 0]] if present else [])
        assert record['state'][0] == 0 and record['state'][1] == 0x807F0000
report = {'result': f'ORIGINAL_{"REPLY_HANDLER" if args.reply_handler else "TRANSPORT"}_NATIVE_PPC{len(cases)}_{"KERNEL_COMPLETION" if args.kernel_completion else "BOUNDARY"}_CASES_PASS', 'records': records,
          'actualKernelCompletions': completion_count,
          'hostSha256': sha(host), 'includedHostSha256': sha(Path('experiments/wii-static-recomp/ios_open_host.cpp')),
          'scriptSha256': sha(Path(__file__)), 'dolSha256': sha(dol_path), 'generatedSha256': sha(base_output / 'selected.cpp'),
          'executableSha256': sha(exe),
          'declarationsSha256': sha(Path('work/private-game/static-recomp/mass-current/functions.h')),
          'analysisSha256': sha(base_output / 'analysis.json'),
          'replyHandler': args.reply_handler,
          'handlerCompletion': args.handler_completion,
          'wakeupCompletion': args.wakeup_completion,
          'limits': ['Queue initialization/cache/IRQ/profiling/register services are explicit fixtures.',
                     'Register read returns provided30; writes record arguments, not actual MMIO delivery.',
                     ('Existing IOSKernel/parser/EventScheduler compute six replies; synthetic sleep release and no-op free, not original IRQ/wakeup/allocator lifecycle.' if args.kernel_completion else
                      'Stop before original sleep/free; no reply/wakeup/IOSKernel/full lifecycle proof.'),
                     'Pending17 is synthetic queue input; invalid-state behavior not broadly verified.',
                     'No ordinary boot activation or physical Wii validation.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
if args.reply_handler:
    report['limits'] = ['Original synchronous OPEN-reply handler execution with prepared MEM1 reply bytes/control inputs.',
                        'Register/MMIO clear/cache-invalidate/wakeup/profiling are explicit fixture services, not real IRQ/OS behavior.',
                        'Async callback/context and other commands not executed; unresolved paths throw.',
                        'No actual thread-switch/wakeup, cache visibility, kernel/scheduler coupling or boot activation.']
    (output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
if args.kernel_completion:
    report['kernelSha256'] = sha(Path(extra_sources[0]))
    report['schedulerSha256'] = sha(Path(extra_sources[1]))
    report['packetAdapterSha256'] = sha(Path('experiments/wii-static-recomp/ipc_open_packet.h'))
    report['replyOracleSha256'] = sha(Path('work/private-game/static-recomp/dolphin-ipc-packet/comparison.json'))
    report['replyDropMutantDetected'] = True
    if args.handler_completion:
        report['result'] = 'ORIGINAL_TRANSPORT_KERNEL_ORIGINAL_REPLY_HANDLER_WAKEUP80_CASES_PASS'
        report['replySourceSha256'] = sha(Path(reply_source[0]))
        report['replyAnalysisSha256'] = sha(Path('work/private-game/static-recomp/ios-reply-handler/analysis.json'))
        report['wakeupDropMutantDetected'] = True
        report['limits'].append('Handler runs on shared MMU; architectural-register save/restore and wakeup token are explicit PC IRQ/thread adaptations, not original vector/OS execution.')
        if args.wakeup_completion:
            report['result'] = 'ORIGINAL_TRANSPORT_KERNEL_REPLY_ORIGINAL_WAKEUP_READY_QUEUE80_CASES_PASS'
            report['wakeupSourceSha256'] = sha(Path(wakeup_source[0]))
            report['wakeupAnalysisSha256'] = sha(Path('work/private-game/static-recomp/ios-wakeup/analysis.json'))
            report['limits'].append('Original wakeup mutates one prepared TCB and run queue; sleep setup/SelectThread/IRQ register preservation/free/cache/MMIO remain adaptations. Release uses queue-state checks, not a wakeup token.')
    (output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS original {"reply handler" if args.reply_handler else "transport"} native/PPC: {len(cases)} cases; OS/IRQ policy remains experimental')
