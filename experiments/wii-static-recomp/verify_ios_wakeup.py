"""Compare original thread-queue wakeup with explicit interrupt/select-thread services."""
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
parser.add_argument('--sleep', action='store_true')
parser.add_argument('--sleep-wakeup', action='store_true')
args = parser.parse_args()
args.sleep |= args.sleep_wakeup

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc
output = Path('work/private-game/static-recomp/ios-sleep' if args.sleep else 'work/private-game/static-recomp/ios-wakeup')
prepare = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--sleep' if args.sleep else '--wakeup', '--compare-so'],
                         capture_output=True, text=True, timeout=180)
assert prepare.returncode == 0, prepare.stderr[-2000:]
base_output = output
extra_sources = []
if args.sleep_wakeup:
    prepare_wake = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--wakeup', '--compare-so'],
                                  capture_output=True, text=True, timeout=180)
    assert prepare_wake.returncode == 0, prepare_wake.stderr[-2000:]
    extra_sources = ['work/private-game/static-recomp/ios-wakeup/selected.cpp']
    output = Path('work/private-game/static-recomp/ios-sleep-wakeup')
    output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/include')
host = Path('experiments/wii-static-recomp/ios_wakeup_host.cpp')
exe = output / 'wakeup-host'
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
                        '-DSHSM_ORIGINAL_ALLOCATOR', '-Wl,-dead_strip', '-I', str(runtime),
                        '-I', 'experiments/wii-static-recomp', '-I', 'work/private-game/static-recomp/mass-current',
                        *(['-DSHSM_SLEEP_THREAD'] if args.sleep else []),
                        *(['-DSHSM_SLEEP_WAKEUP'] if args.sleep_wakeup else []),
                        str(host), str(base_output / 'selected.cpp'), *extra_sources, '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'host-build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-2000:]
cases = list(itertools.product([0, 1, 2, 3], [0, 7, 31], [0, 1, 3, 7], [0, 1], [0, 0xA0000000]))
if args.sleep:
    cases = list(itertools.product([0, 1, 2, 3], [0, 7, 31], [0, 1, 2], [0, 1], [0, 0xA0000000]))
native = subprocess.run([str(exe.resolve())], input=''.join(' '.join(map(str, case)) + '\n' for case in cases),
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
for i in range(18):
    if header[36 + i]:
        uc.mem_write(header[18 + i], dol[header[i]:header[i] + header[36 + i]])
regs = [getattr(ppc, f'UC_PPC_REG_{i}') for i in range(32)]
events = []


def observe(machine, pc, size, data):
    if pc in (0x807F0100, 0x807F0104):
        return
    if pc in (0x802174E0, 0x80217520, 0x8021A790):
        kind = {0x802174E0: 3, 0x80217520: 4, 0x8021A790: 30}[pc]
        events.extend([kind, 0 if kind == 3 else uc.reg_read(regs[3]), 0, 0])
        if kind == 3:
            uc.reg_write(regs[3], 0)
        uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
        return
    assert (0x8021B4E0 <= pc < 0x8021B6C8 if args.sleep_wakeup else
            0x8021B4E0 <= pc < 0x8021B5D0 if args.sleep else 0x8021B5D0 <= pc < 0x8021B6C8), hex(pc)


uc.hook_add(UC_HOOK_CODE, observe)
spans = [(0x806A004C, 8), (0x80680000, 4096), (0x80690000, 1024), (0x80492970, 256), (0x8052AB04, 8), (0x806FFFC0, 96)]
store = lambda address, value: uc.mem_write(address, struct.pack('>I', value))
load = lambda address: struct.unpack('>I', uc.mem_read(address, 4))[0]
records = []
for case, row in zip(cases, rows):
    count, priority, suspended, existing, xer = case
    for address, size in spans:
        uc.mem_write(address, bytes(size))
    store(0x806A004C, 0x80680000 if count else 0)
    store(0x806A0050, 0x80680000 + (count - 1) * 1024 if count else 0)
    for i in range(count):
        thread = 0x80680000 + i * 1024
        uc.mem_write(thread + 0x2C8, struct.pack('>H', 4))
        for offset, value in [(0x2CC, (suspended >> i) & 1), (0x2D0, priority), (0x2DC, 0x806A004C),
                              (0x2E0, thread + 1024 if i + 1 < count else 0), (0x2E4, thread - 1024 if i else 0)]:
            store(thread + offset, value)
        if args.sleep:
            store(thread + 0x2CC, 0)
            store(thread + 0x2D0, 7 if suspended == 0 else [0, 7, 31][i] if suspended == 1 else 31)
    if args.sleep:
        store(0x800000E4, 0x80690000)
        uc.mem_write(0x806902C8, struct.pack('>H', 4 if existing else 2))
        store(0x806902D0, priority)
    elif existing:
        store(0x80492970 + priority * 8, 0x80690000)
        store(0x80492974 + priority * 8, 0x80690000)
    for i, register in enumerate(regs):
        uc.reg_write(register, 0x12340000 + i)
    for i, value in [(1, 0x80700000), (3, 0x806A004C), (13, 0x8052E720)]:
        uc.reg_write(regs[i], value)
    for register, value in [(ppc.UC_PPC_REG_LR, 0x807F0000), (ppc.UC_PPC_REG_CTR, 0), (ppc.UC_PPC_REG_CR, 0)]:
        uc.reg_write(register, value)
    uc.mem_write(0x807F0100, struct.pack('>II', 0x7FE103A6, 0x7FE102A6))
    uc.reg_write(regs[31], xer)
    uc.emu_start(0x807F0100, 0x807F0104, count=1)
    uc.reg_write(regs[31], 0x1234001F)
    events.clear()
    uc.emu_start(0x8021B4E0 if args.sleep else 0x8021B5D0, 0x807F0000, count=2000)
    if args.sleep_wakeup:
        uc.reg_write(regs[3], 0x806A004C)
        uc.reg_write(ppc.UC_PPC_REG_LR, 0x807F0000)
        uc.emu_start(0x8021B5D0, 0x807F0000, count=2000)
    pc, saved31 = uc.reg_read(ppc.UC_PPC_REG_PC), uc.reg_read(regs[31])
    uc.emu_start(0x807F0104, 0x807F0108, count=1)
    observed_xer = uc.reg_read(regs[31])
    uc.reg_write(regs[31], saved31)
    state = [pc, uc.reg_read(ppc.UC_PPC_REG_LR), uc.reg_read(ppc.UC_PPC_REG_CTR), observed_xer,
             uc.reg_read(ppc.UC_PPC_REG_CR)] + [uc.reg_read(reg) for reg in regs]
    memory = b''.join(bytes(uc.mem_read(address, size)) for address, size in spans).hex()
    assert list(map(int, row[:-1])) == state + [len(events)] + events and row[-1] == memory, (case, row[:-1], state)
    if args.sleep:
        old = [0x80680000 + i * 1024 for i in range(count)]
        index = next((i for i, thread in enumerate(old) if load(thread + 0x2D0) > priority), len(old))
        ordered = old[:index] + [0x80690000] + old[index:]
        if args.sleep_wakeup:
            assert pc == 0x807F0000 and load(0x806A004C) == load(0x806A0050) == 0
            expected_bits = 0
            for p in (0, 7, 31):
                members = [thread for thread in ordered if load(thread + 0x2D0) == p]
                queue = 0x80492970 + p * 8
                assert load(queue) == (members[0] if members else 0)
                assert load(queue + 4) == (members[-1] if members else 0)
                for i, thread in enumerate(members):
                    assert bytes(uc.mem_read(thread + 0x2C8, 2)) == b'\x00\x01'
                    assert load(thread + 0x2DC) == queue
                    assert load(thread + 0x2E0) == (members[i + 1] if i + 1 < len(members) else 0)
                    assert load(thread + 0x2E4) == (members[i - 1] if i else 0)
                if members:
                    expected_bits |= 1 << (31 - p)
            assert load(0x8052AB08) == expected_bits and load(0x8052AB04) == 1
            assert [events[i] for i in range(0, len(events), 4)] == [3, 30, 4, 3, 30, 4]
            records.append({'input': case, 'state': state, 'events': list(events), 'memoryHex': memory})
            continue
        assert pc == 0x807F0000 and load(0x806A004C) == ordered[0] and load(0x806A0050) == ordered[-1]
        assert load(0x8052AB04) == 1 and load(0x8052AB08) == 0
        assert bytes(uc.mem_read(0x806902C8, 2)) == b'\x00\x04'
        for i, thread in enumerate(ordered):
            assert load(thread + 0x2DC) == 0x806A004C
            assert load(thread + 0x2E0) == (ordered[i + 1] if i + 1 < len(ordered) else 0)
            assert load(thread + 0x2E4) == (ordered[i - 1] if i else 0)
        assert [events[i] for i in range(0, len(events), 4)] == [3, 30, 4]
        records.append({'input': case, 'state': state, 'events': list(events), 'memoryHex': memory})
        continue
    runnable = [0x80680000 + i * 1024 for i in range(count) if not (suspended >> i) & 1]
    assert pc == 0x807F0000 and load(0x806A004C) == load(0x806A0050) == 0
    assert load(0x8052AB08) == ((1 << (31 - priority)) if runnable else 0)
    assert load(0x8052AB04) == bool(runnable)
    assert [events[i] for i in range(0, len(events), 4)] == ([3, 30, 4] if runnable else [3, 4])
    for i in range(count):
        assert bytes(uc.mem_read(0x80680000 + i * 1024 + 0x2C8, 2)) == b'\x00\x01'
    if runnable:
        assert load(0x80492970 + priority * 8) == (0x80690000 if existing else runnable[0])
        assert load(0x80492974 + priority * 8) == runnable[-1]
    records.append({'input': case, 'state': state, 'events': list(events), 'memoryHex': memory})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': f'ORIGINAL_WAKEUP_NATIVE_PPC{len(cases)}_QUEUE_CASES_PASS', 'records': records,
          'hostSha256': sha(host), 'includedHostSha256': sha(Path('experiments/wii-static-recomp/ios_open_host.cpp')),
          'scriptSha256': sha(Path(__file__)), 'dolSha256': sha(dol_path), 'analysisSha256': sha(base_output / 'analysis.json'),
          'generatedSha256': sha(base_output / 'selected.cpp'), 'executableSha256': sha(exe),
          'carryHelperSha256': sha(Path('experiments/wii-static-recomp/carry_adapter.h')),
          'carryLoweringSha256': sha(Path('experiments/wii-static-recomp/carry_lowering.py')),
          'compareLoweringSha256': sha(Path('experiments/wii-static-recomp/compare_so_lowering.py')),
          'limits': ['Prepared queues/TCB fields; original wakeup body executes, OS interrupt/SelectThread services are fixtures.',
                     '0..3 waiting nodes, same-priority queues, suspended counts0/1 only; general thread lifecycle and malformed lists unverified.',
                     'SelectThread only records its call; no real CPU/context switch, IRQ delivery or scheduler activation.',
                     'Isolated component, not yet coupled to original transport/kernel/reply-handler tests or full boot.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
if args.sleep:
    report['result'] = f'ORIGINAL_SLEEP_NATIVE_PPC{len(cases)}_PRIORITY_QUEUE_CASES_PASS'
    report['limits'] = ['Original sleep body inserts prepared current TCB in sorted wait queue; interrupt/SelectThread services are fixtures.',
                        '0..3 nodes, priorities0/7/31, ascending/equal profiles; ties preserve existing node order.',
                        'Provided SelectThread returns while TCB remains waiting; not actual blocking/resumption or context transfer.',
                        'No wakeup/transport integration, physical Wii trace, malformed lists, idle/IRQ or ordinary boot activation.']
    (output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
if args.sleep_wakeup:
    report['result'] = 'ORIGINAL_SLEEP_WAKEUP144_PRIORITY_QUEUE_CASES_PASS'
    report['wakeupGeneratedSha256'] = sha(Path(extra_sources[0]))
    report['wakeupAnalysisSha256'] = sha(Path('work/private-game/static-recomp/ios-wakeup/analysis.json'))
    report['limits'] = ['Original sleep insertion and wakeup on one shared MMU, host-directed calls; no manual wait-node insertion between calls.',
                        'Mixed/equal prepared priorities0/7/31; all waiting nodes nonsuspended.',
                        'SelectThread and interrupt services remain provided; no blocking/context resumption/IRQ/transport or full boot.']
    (output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
stage = 'sleep→wakeup' if args.sleep_wakeup else 'sleep insertion' if args.sleep else 'wakeup'
print(f'PASS original {stage} native/PPC: {len(cases)} queue cases; real SelectThread remains unverified')
