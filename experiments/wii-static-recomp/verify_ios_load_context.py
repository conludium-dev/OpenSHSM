"""Compare original context restoration through RFI with a PPC750CL instruction oracle."""
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

parser = argparse.ArgumentParser()
parser.add_argument('--save-roundtrip', action='store_true')
parser.add_argument('--save-only', action='store_true')
parser.add_argument('--external-irq', action='store_true')
args = parser.parse_args()
args.save_roundtrip |= args.save_only
assert not args.external_irq or not args.save_roundtrip

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn import ppc_const as ppc

output = Path('work/private-game/static-recomp/ios-load-context')
prepared = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--load-context'],
                          capture_output=True, text=True, timeout=180)
assert prepared.returncode == 0, prepared.stderr[-2000:]
base_output = output
extra_sources = []
if args.save_roundtrip:
    prepared_save = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--save-context'],
                                   capture_output=True, text=True, timeout=180)
    assert prepared_save.returncode == 0, prepared_save.stderr[-2000:]
    extra_sources = ['work/private-game/static-recomp/ios-save-context/selected.cpp']
    output = Path('work/private-game/static-recomp/ios-save-only' if args.save_only else 'work/private-game/static-recomp/ios-save-load-roundtrip')
    output.mkdir(exist_ok=True)
priority_words = []
irq_sources = []
if args.external_irq:
    output = Path('work/private-game/static-recomp/ios-external-irq')
    output.mkdir(exist_ok=True)
    for mode in ('irq-dispatch', 'save-context', 'set-context'):
        prepared_irq = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--' + mode,
                                       *(['--compare-so'] if mode != 'save-context' else [])], capture_output=True, text=True, timeout=180)
        assert prepared_irq.returncode == 0, prepared_irq.stderr[-2000:]
        extra_sources.append('work/private-game/static-recomp/ios-' + mode + '/selected.cpp')
    helper = Path('work/private-game/static-recomp/ios-thread-cycle-ipc-irq/helpers.cpp')
    predecessor = json.loads(Path('work/private-game/static-recomp/ios-thread-cycle-ipc-irq/comparison.json').read_text())
    assert predecessor['sources'][str(helper)] == hashlib.sha256(helper.read_bytes()).hexdigest()
    extra_sources.append(str(helper))
    original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
    assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
    original_header = struct.unpack('>64I', original[:256])
    def original_word(address):
        i = next(i for i in range(18) if original_header[18 + i] <= address < original_header[18 + i] + original_header[36 + i])
        return struct.unpack_from('>I', original, original_header[i] + address - original_header[18 + i])[0]
    priority_words = [original_word(0x8042CF98 + i * 4) for i in range(12)]
    parent = Path('work/private-game/static-recomp/mass-current/output_63.cpp').read_text()
    scheduler_bodies = []
    for entry in (0x8021A460, 0x8021A4A0):
        start = parent.index(f'void func_{entry:08X}(CPUContext& ctx) {{')
        end = parent.index('\nvoid func_', start + 1)
        body = parent[start:end]
        markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body)
        assert [int(pc, 16) for pc, word in markers] == list(range(entry, entry + 60, 4))
        assert all(original_word(int(pc, 16)) == int(word, 16) for pc, word in markers)
        scheduler_bodies.append(body)
    scheduler = output / 'scheduler.cpp'
    scheduler.write_text(parent[:parent.index('void func_')] + '\n'.join(scheduler_bodies))
    extra_sources.append(str(scheduler))
    upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
    irq_sources = [str(upstream / 'src/hw/hw_pi.cpp'), str(upstream / 'src/hw/mmio_dispatcher.cpp')]
host = Path('experiments/wii-static-recomp/ios_load_context_host.cpp')
exe = output / 'load-host'
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-Wl,-dead_strip',
                        '-I', '_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/include',
                        '-I', 'experiments/wii-static-recomp', '-I', 'work/private-game/static-recomp/mass-current',
                        *(['-DSHSM_SAVE_ROUNDTRIP'] if args.save_roundtrip else []),
                        *(['-DSHSM_SAVE_ONLY'] if args.save_only else []),
                        *(['-DSHSM_EXTERNAL_IRQ_TEST', '-DSHSM_ORIGINAL_ALLOCATOR', '-DSHSM_ORIGINAL_IRQ_SERVICES'] if args.external_irq else []),
                        str(host), str(base_output / 'selected.cpp'), *extra_sources, *irq_sources, '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'host-build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-2000:]
cases = list(itertools.product([0x807F0000, 0x802174E0, 0x802174E4, 0x802174E8, 0x802174EC, 0x802174F0],
                              [0, 2, 3, 0xFFFF], [0, 2, 0x2000, 0x2002], [0, 0xA0000000], [0, 1]))
if args.save_roundtrip:
    cases = [case for case in cases if case[1] == 0]
if args.external_irq:
    cases = [case + (irq_case,) for case in cases if case[0] == 0x807F0000 and case[1] in (2, 3) for irq_case in range(6)]
native = subprocess.run([str(exe.resolve())], input=''.join(' '.join(map(str, (*case, *priority_words))) + '\n' for case in cases),
                        capture_output=True, text=True, timeout=60)
(output / 'native.log').write_text(native.stdout + native.stderr)
assert native.returncode == 0, native.stderr[-2000:]
rows = [row.split() for row in native.stdout.splitlines()]
assert len(rows) == len(cases)
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
if args.external_irq:
    uc.mem_map(0xCC000000, 65536)
for i in range(18):
    if header[36 + i]:
        uc.mem_write(header[18 + i], dol[header[i]:header[i] + header[36 + i]])
regs = [getattr(ppc, f'UC_PPC_REG_{i}') for i in range(32)]
store = lambda address, value: uc.mem_write(address, struct.pack('>I', value))
load = lambda address: struct.unpack('>I', uc.mem_read(address, 4))[0]
target_pc = None
events = []
irq_spans = [(0x806FFFC0, 96), (0x800000C4, 8), (0x80003040, 128), (0x8052AAC8, 20), (0x8052AB00, 8), (0x8042CF98, 48)]


def observe(machine, pc, size, data):
    if 0x807F3000 <= pc < 0x807F3040:
        return
    if pc == target_pc:
        uc.emu_stop()
        return
    if args.external_irq:
        if pc == 0x8021C000:
            uc.reg_write(regs[3], 1)
            uc.reg_write(regs[4], 0x23456789)
            events.extend([42, 1, 0x23456789, 0])
            uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
            return
        if pc == 0x807F4000:
            assert irq_case == 5 and uc.reg_read(regs[3]) == 27 and uc.reg_read(regs[4]) == 0x80680000
            assert uc.reg_read(ppc.UC_PPC_REG_LR) == 0x80217C24 and load(0x8052AB00) == 1
            events.extend([40, 27, 0x80680000, 1])
            uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
            return
        assert (0x802179B0 <= pc < 0x80217CB0 or 0x80213920 <= pc < 0x802139F8
                or 0x802174E0 <= pc < 0x802174F4 or 0x80217520 <= pc < 0x80217544
                or 0x8021A460 <= pc < 0x8021A49C or 0x8021A4A0 <= pc < 0x8021A4DC
                or 0x8021A9C0 <= pc < 0x8021A9D4), hex(pc)
        return
    assert 0x802138A0 <= pc < 0x802139F8 if args.save_roundtrip else 0x80213920 <= pc < 0x802139F8, hex(pc)


uc.hook_add(UC_HOOK_CODE, observe)
if args.external_irq:
    def observe_pi(machine, access, address, size, value, data):
        if address >= 0xCC000000:
            assert address in (0xCC003000, 0xCC003004) and size == 4
            events.extend([41, address & 0x1FFFFFFF, load(address), 0])
    uc.hook_add(UC_HOOK_MEM_READ, observe_pi)


def read_spr(number):
    saved = uc.reg_read(regs[31])
    store(0x807F3000, 0x7FE002A6 | (number & 31) << 16 | (number >> 5) << 11)
    uc.emu_start(0x807F3000, 0x807F3004, count=1)
    result = uc.reg_read(regs[31])
    uc.reg_write(regs[31], saved)
    return result


def write_spr(number, value):
    saved = uc.reg_read(regs[31])
    uc.reg_write(regs[31], value)
    store(0x807F3000, 0x7FE003A6 | (number & 31) << 16 | (number >> 5) << 11)
    uc.emu_start(0x807F3000, 0x807F3004, count=1)
    uc.reg_write(regs[31], saved)


records = []
for case, row in zip(cases, rows):
    target, flags, msr, xer, seed = case[:5]
    events.clear()
    base = 0x80680000
    uc.mem_write(base, bytes(1024))
    for i, register in enumerate(regs):
        uc.reg_write(register, 0x12340000 + i)
        store(base + i * 4, 0x56780000 + seed * 0x100 + i)
    for offset, value in [(4, 0x80700000), (0x80, 0x87654321 if seed else 0),
                          (0x84, 0x807F1000 + seed * 4), (0x88, 0x13570000 + seed), (0x8C, xer),
                          (0x198, target), (0x19C, msr)]:
        store(base + offset, value)
    uc.mem_write(base + 0x1A2, struct.pack('>H', flags))
    for i in range(1, 8):
        store(base + 0x1A4 + i * 4, 0x10000 * seed + i)
    uc.reg_write(regs[3], base)
    for register, value in [(ppc.UC_PPC_REG_LR, 0x807F2000), (ppc.UC_PPC_REG_CTR, 0),
                            (ppc.UC_PPC_REG_CR, 0), (ppc.UC_PPC_REG_MSR, 0x2002)]:
        uc.reg_write(register, value)
    target_pc = 0x802174E0 if 0x802174E0 < target < 0x802174EC else target
    if args.external_irq:
        irq_case = case[5]
        for address, size in irq_spans:
            uc.mem_write(address, bytes(size))
        for i, word in enumerate(priority_words):
            store(0x8042CF98 + i * 4, word)
        for address, value in [(0x8052AAD8, 0x80003040), (0x800030AC, 0x807F4000 if irq_case == 5 else 0),
                               (0x800000C4, 0x10 if irq_case == 2 else 0), (0x800000C8, 0x10 if irq_case == 3 else 0),
                               (0xCC003000, 0x10000 if irq_case == 0 else 0x14000), (0xCC003004, 0 if irq_case == 1 else 0x4000)]:
            store(address, value)
        for i, value in [(1, 0x80700000), (3, 4), (4, base), (13, 0x8052E720)]:
            uc.reg_write(regs[i], value)
        write_spr(1, xer)
        for i in range(1, 8):
            write_spr(912 + i, 0x20000 * seed + i)
    if args.save_roundtrip:
        uc.reg_write(regs[1], 0x80700000)
        uc.reg_write(ppc.UC_PPC_REG_LR, target)
        uc.reg_write(ppc.UC_PPC_REG_CTR, 0x13570000 + seed)
        uc.reg_write(ppc.UC_PPC_REG_CR, 0x87654321 if seed else 0)
        uc.reg_write(ppc.UC_PPC_REG_MSR, msr)
        for spr, value in [(1, xer), (26, 0), (27, 0), *[(912 + i, 0x10000 * seed + i) for i in range(1, 8)]]:
            write_spr(spr, value)
        target_pc = target
        uc.emu_start(0x802138A0, 0x807F0004, count=500)
        assert uc.reg_read(regs[3]) == 0 and load(base + 12) == 1
        if not args.save_only:
            uc.reg_write(regs[3], base)
            target_pc = 0x802174E0 if 0x802174E0 < target < 0x802174EC else target
    if not args.save_only:
        uc.emu_start(0x80217C60 if args.external_irq else 0x80213920, 0x807F0004, count=2000 if args.external_irq else 500)
    state = [uc.reg_read(ppc.UC_PPC_REG_PC), uc.reg_read(ppc.UC_PPC_REG_LR), uc.reg_read(ppc.UC_PPC_REG_CTR),
             read_spr(1), uc.reg_read(ppc.UC_PPC_REG_CR), uc.reg_read(ppc.UC_PPC_REG_MSR)]
    state += [uc.reg_read(reg) for reg in regs]
    state += [read_spr(26), read_spr(27)] + [read_spr(912 + i) for i in range(1, 8)]
    memory = bytes(uc.mem_read(base, 1024)).hex()
    if args.external_irq:
        memory += b''.join(bytes(uc.mem_read(address, size)) for address, size in irq_spans).hex()
    assert list(map(int, row[:-1])) == state + [len(events)] + events and row[-1] == memory, (case, row[:-1], state)
    assert state[0] == target_pc and state[3] == xer and state[4] == (0x87654321 if seed else 0)
    assert load(base + 0x198) == target_pc
    assert int.from_bytes(uc.mem_read(base + 0x1A2, 2), 'big') == flags & ~2
    if args.save_only:
        assert state[6] == 1 and state[9] == 0
        assert load(base + 4) == 0x80700000 and load(base + 8) == 0x12340002
        assert load(base + 12) == 1 and load(base + 0x19C) == msr
        for i in range(13, 32):
            assert load(base + i * 4) == 0x12340000 + i
    else:
        for i in [0, 1, 2, 3, 4, *range(13 if not flags & 2 else 5, 32)]:
            assert state[6 + i] == load(base + i * 4), (case, i)
        if args.save_roundtrip:
            assert state[9] == 1 and state[7] == 0x80700000
    if args.external_irq:
        assert load(0x8052AB00) == load(0x8052AB04) == 0
        assert [events[i] for i in range(0, len(events), 4)] == ([41, 41, 42, 40] if irq_case == 5 else [41, 41])
        if irq_case == 5:
            assert load(0x8052AAC8) == target and int.from_bytes(uc.mem_read(0x8052AACC, 2), 'big') == 27
            assert load(0x8052AAD0) == 1 and load(0x8052AAD4) == 0x23456789
    records.append({'input': case, 'state': state, 'events': list(events), 'memoryHex': memory})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': 'ORIGINAL_OSLOADCONTEXT_NATIVE_PPC_CASES_PASS', 'cases': len(cases), 'records': records,
          'hostSha256': sha(host), 'includedHostSha256': sha(Path('experiments/wii-static-recomp/ios_open_host.cpp')),
          'scriptSha256': sha(Path(__file__)), 'dolSha256': sha(dol_path), 'analysisSha256': sha(base_output / 'analysis.json'),
          'generatedSha256': sha(base_output / 'selected.cpp'), 'executableSha256': sha(exe),
          'limits': ['Prepared standalone OSContext, saved MSR only FP/RI with EE0; original RFI executes.',
                     'No actual save/selector/wakeup integration or physical Wii trace.',
                     'No EE1 IRQ delivery, FPU data restoration, full MSR legality, idle wait or ordinary boot activation.']}
if args.save_roundtrip:
    report['result'] = 'ORIGINAL_OSSAVECONTEXT_ONLY_CASES_PASS' if args.save_only else 'ORIGINAL_SAVE_LOAD_ROUNDTRIP_CASES_PASS'
    report['saveGeneratedSha256'] = sha(Path(extra_sources[0]))
    report['saveAnalysisSha256'] = sha(Path('work/private-game/static-recomp/ios-save-context/analysis.json'))
    report['limits'] = ['Original context save and optional load execute on one CPUContext/MMU; host-directed sequence.',
                        'No actual selector/wakeup/IRQ/physical Wii trace; flags0 and MSR FP/RI/EE0 only.',
                        'FPU lifecycle, ordinary boot, resumed caller execution and general MSR legality unverified.']
if args.external_irq:
    report['result'] = 'ORIGINAL_EXTERNAL_IRQ_PI_MASK_TABLE_CALLBACK_RFI192_CASES_PASS'
    report['memoryBytesPerCase'] = 1024 + sum(size for address, size in irq_spans)
    report['extraSourceHashes'] = {str(path): sha(Path(path)) for path in extra_sources + irq_sources}
    report['priorityTableSha256'] = hashlib.sha256(struct.pack('>12I', *priority_words)).hexdigest()
    report['limits'] = ['Original external save/dispatcher/scheduler disable-enable/IRQ primitives/context load/RFI execute; reschedule hint0 only.',
                        'PI cause/mask seeded on existing vendor PI; low software masks/table/context prepared, not original initializer/vector preamble.',
                        'Selected IRQ27 handler and OSGetTime are explicit test services; no actual IPC reply/wakeup/vector delivery/EE1/FPU lifecycle/full boot.']
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
stage = 'ExternalInterruptHandler→dispatcher→OSLoadContext/RFI' if args.external_irq else 'OSSaveContext' if args.save_only else 'OSSaveContext→OSLoadContext' if args.save_roundtrip else 'OSLoadContext'
print(f'PASS original {stage}: {len(cases)} PPC/native cases; full thread/IRQ switch unverified')
