"""Compare original selection, optionally executing its initial callback before context loading."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import struct
import subprocess
import sys
import argparse
import re

parser = argparse.ArgumentParser()
parser.add_argument('--default-callback', action='store_true')
parser.add_argument('--set-context', action='store_true')
parser.add_argument('--context-transfer', action='store_true')
args = parser.parse_args()
args.set_context |= args.context_transfer
args.default_callback |= args.set_context

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc
output = Path('work/private-game/static-recomp/ios-select-thread')
base_output = output
if args.default_callback:
    output = Path('work/private-game/static-recomp/ios-select-default-callback')
    output.mkdir(exist_ok=True)
if args.set_context:
    output = Path('work/private-game/static-recomp/ios-select-set-context')
    output.mkdir(exist_ok=True)
if args.context_transfer:
    output = Path('work/private-game/static-recomp/ios-selector-context-transfer')
    output.mkdir(exist_ok=True)
prepared = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--select-thread', '--compare-so'],
                          capture_output=True, text=True, timeout=180)
assert prepared.returncode == 0, prepared.stderr[-2000:]
extra_sources = []
if args.default_callback:
    source = Path('work/private-game/static-recomp/mass-current/output_63.cpp')
    text = source.read_text()
    start = text.index('void func_8021A1A0(CPUContext& ctx) {')
    end = text.index('\nvoid func_', start + 1)
    assert re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', text[start:end]) == [('8021A1A0', '4E800020')]
    callback = output / 'default-callback.cpp'
    callback.write_text(text[:text.index('void func_')] + text[start:end])
    extra_sources = [str(callback)]
if args.set_context:
    prepared_context = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--set-context', '--compare-so'],
                                      capture_output=True, text=True, timeout=180)
    assert prepared_context.returncode == 0, prepared_context.stderr[-2000:]
    start = text.index('void func_80213890(CPUContext& ctx) {')
    end = text.index('\nvoid func_', start + 1)
    assert re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', text[start:end]) == [
        ('80213890', '3C608000'), ('80213894', '806300D4'), ('80213898', '4E800020')]
    getter = output / 'context-getter.cpp'
    getter.write_text(text[:text.index('void func_')] + text[start:end])
    extra_sources += [str(getter), 'work/private-game/static-recomp/ios-set-context/selected.cpp']
if args.context_transfer:
    for mode in ('save-context', 'load-context'):
        prepared_body = subprocess.run(['python3', 'experiments/wii-static-recomp/analyze_ios_transport.py', '--' + mode],
                                       capture_output=True, text=True, timeout=180)
        assert prepared_body.returncode == 0, prepared_body.stderr[-2000:]
        extra_sources.append('work/private-game/static-recomp/ios-' + mode + '/selected.cpp')
host = Path('experiments/wii-static-recomp/ios_select_thread_host.cpp')
exe = output / 'select-host'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/include')
build = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-Wl,-dead_strip', '-DSHSM_ORIGINAL_ALLOCATOR',
                        '-I', str(runtime), '-I', 'experiments/wii-static-recomp', '-I', 'work/private-game/static-recomp/mass-current',
                        *(['-DSHSM_DEFAULT_SWITCH_CALLBACK'] if args.default_callback else []),
                        *(['-DSHSM_ORIGINAL_SET_CONTEXT'] if args.set_context else []),
                        *(['-DSHSM_CONTEXT_TRANSFER'] if args.context_transfer else []),
                        str(host), str(base_output / 'selected.cpp'), *extra_sources, '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'host-build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr[-2000:]
cases = list(itertools.product([0, 1], [0, 2, 4], [0, 7, 31], [0, 7, 31], [0, 1], [0, 0xA0000000]))
if args.set_context:
    cases = [case + (owner, msr) for case in cases for owner, msr in itertools.product([0, 1, 2], [0, 0x2000])]
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
if args.default_callback:
    def original_word(address):
        i = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        return struct.unpack_from('>I', dol, header[i] + address - header[18 + i])[0]
    assert original_word(0x80528A30) == 0x8021A1A0
    assert original_word(0x8021A1A0) == 0x4E800020
    if args.set_context:
        assert [original_word(pc) for pc in (0x80213890, 0x80213894, 0x80213898)] == [0x3C608000, 0x806300D4, 0x4E800020]
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for i in range(18):
    if header[36 + i]:
        uc.mem_write(header[18 + i], dol[header[i]:header[i] + header[36 + i]])
regs = [getattr(ppc, f'UC_PPC_REG_{i}') for i in range(32)]
events = []
stop_addresses = (0x807F0300, 0x80213830, 0x80213920, 0x80213A70, 0x80217500)
if args.set_context:
    stop_addresses = tuple(pc for pc in stop_addresses if pc != 0x80213830)
if args.context_transfer:
    stop_addresses = tuple(pc for pc in stop_addresses if pc != 0x80213920) + (0x807F4000,)


def observe(machine, pc, size, data):
    if 0x807F0100 <= pc < 0x807F0120:
        return
    if pc in stop_addresses:
        uc.emu_stop()
        return
    if pc == 0x802138A0 and not args.context_transfer or pc == 0x80213890 and not args.set_context:
        events.extend([31, 0, 0, 0] if pc == 0x80213890 else [32, uc.reg_read(regs[3]), 0, 0])
        uc.reg_write(regs[3], load(0x800000E4) if pc == 0x80213890 else 0)
        uc.reg_write(ppc.UC_PPC_REG_PC, uc.reg_read(ppc.UC_PPC_REG_LR))
        return
    assert (0x8021A790 <= pc < 0x8021A9BC or args.default_callback and pc == 0x8021A1A0
            or args.set_context and (0x80213830 <= pc < 0x8021388C or 0x80213890 <= pc < 0x8021389C)
            or args.context_transfer and 0x802138A0 <= pc < 0x802139F8), hex(pc)


uc.hook_add(UC_HOOK_CODE, observe)
spans = [(0x80680000, 1024), (0x80690000, 1024), (0x80492970, 256), (0x8052AB00, 12), (0x800000E4, 4), (0x806FFFC0, 96)]
if args.set_context:
    spans.append((0x800000C0, 28))
store = lambda address, value: uc.mem_write(address, struct.pack('>I', value))
load = lambda address: struct.unpack('>I', uc.mem_read(address, 4))[0]


def spr_access(number, value=None):
    saved = uc.reg_read(regs[31])
    if value is not None:
        uc.reg_write(regs[31], value)
    store(0x807F0110, (0x7FE002A6 if value is None else 0x7FE003A6) | (number & 31) << 16 | (number >> 5) << 11)
    uc.emu_start(0x807F0110, 0x807F0114, count=1)
    result = uc.reg_read(regs[31])
    uc.reg_write(regs[31], saved)
    return result


records = []
for case, row in zip(cases, rows):
    disabled, current_state, current_priority, next_priority, forced_yield, xer = case[:6]
    for address, size in spans:
        uc.mem_write(address, bytes(size))
    if args.set_context:
        owner, msr = case[6:]
        store(0x800000D4, 0x80690000 if current_state else 0)
        store(0x800000D8, [0, 0x80680000, 0x80690000][owner])
        store(0x8068019C, msr)
        store(0x8069019C, msr)
        uc.reg_write(ppc.UC_PPC_REG_MSR, msr)
    if args.context_transfer:
        for base in (0x80680000, 0x80690000):
            for i in range(32):
                store(base + i * 4, 0x56780000 + i)
            for offset, value in [(4, 0x806FF000), (12, 1), (52, 0x8052E720), (0x80, 0x87654321),
                                  (0x84, 0x807F5000), (0x88, 0x13570000), (0x8C, xer), (0x198, 0x807F4000)]:
                store(base + offset, value)
            for i in range(1, 8):
                store(base + 0x1A4 + i * 4, i)
        for number in (26, 27, *range(913, 920)):
            spr_access(number, 0)
    for address, value in [(0x8052AB00, disabled), (0x8052AB04, 1), (0x8052AB08, 1 << (31 - next_priority)),
                           (0x80528A30, 0x8021A1A0 if args.default_callback else 0x807F0300), (0x800000E4, 0x80690000 if current_state else 0),
                           (0x806902D0, current_priority), (0x806802D0, next_priority),
                           (0x806802DC, 0x80492970 + next_priority * 8),
                           (0x80492970 + next_priority * 8, 0x80680000), (0x80492974 + next_priority * 8, 0x80680000)]:
        store(address, value)
    uc.mem_write(0x806902C8, struct.pack('>H', current_state))
    uc.mem_write(0x806802C8, b'\x00\x01')
    for i, register in enumerate(regs):
        uc.reg_write(register, 0x12340000 + i)
    for i, value in [(1, 0x80700000), (3, forced_yield), (13, 0x8052E720)]:
        uc.reg_write(regs[i], value)
    for register, value in [(ppc.UC_PPC_REG_LR, 0x807F0000), (ppc.UC_PPC_REG_CTR, 0), (ppc.UC_PPC_REG_CR, 0)]:
        uc.reg_write(register, value)
    uc.mem_write(0x807F0100, struct.pack('>II', 0x7FE103A6, 0x7FE102A6))
    uc.reg_write(regs[31], xer)
    uc.emu_start(0x807F0100, 0x807F0104, count=1)
    uc.reg_write(regs[31], 0x1234001F)
    events.clear()
    uc.emu_start(0x8021A790, 0x807F0000, count=2000)
    pc, saved31 = uc.reg_read(ppc.UC_PPC_REG_PC), uc.reg_read(regs[31])
    uc.emu_start(0x807F0104, 0x807F0108, count=1)
    observed_xer = uc.reg_read(regs[31])
    uc.reg_write(regs[31], saved31)
    state = [pc, uc.reg_read(ppc.UC_PPC_REG_LR), uc.reg_read(ppc.UC_PPC_REG_CTR), observed_xer,
             uc.reg_read(ppc.UC_PPC_REG_CR)] + [uc.reg_read(reg) for reg in regs]
    if args.set_context:
        state.append(uc.reg_read(ppc.UC_PPC_REG_MSR))
    if args.context_transfer:
        state += [spr_access(26), spr_access(27)] + [spr_access(i) for i in range(913, 920)]
    memory = b''.join(bytes(uc.mem_read(address, size)) for address, size in spans).hex()
    assert list(map(int, row[:-1])) == state + [len(events)] + events and row[-1] == memory, (case, row[:-1], state)
    assert pc in (0x807F0000, *stop_addresses)
    if disabled or (current_state == 2 and not forced_yield and current_priority <= next_priority):
        assert pc == 0x807F0000 and state[8] == 0
    else:
        assert pc in ((0x807F0000, 0x807F4000) if args.context_transfer else
                      (0x80213920 if args.set_context else 0x80213830 if args.default_callback else 0x807F0300,))
        selected = load(0x800000E4) if args.context_transfer else state[8] if args.set_context else state[9]
        assert selected in (0x80680000, 0x80690000)
        assert bytes(uc.mem_read(selected + 0x2C8, 2)) == b'\x00\x02'
        assert load(selected + 0x2DC) == 0
        assert load(0x800000E4) == (selected if args.default_callback else 0x80690000 if current_state else 0)
        if args.set_context:
            assert load(0x800000D4) == selected and load(0x800000C0) == selected & 0x3FFFFFFF
            same_owner = load(0x800000D8) == selected
            assert load(selected + 0x19C) == ((msr | 0x2000) if same_owner else msr & ~0x2000)
            if args.context_transfer:
                assert state[37] == load(selected + 0x19C)
                if current_state:
                    assert load(0x80690198) == 0x8021A890 and load(0x8069000C) == 1
                    assert load(0x80690004) == 0x806FFFF0
                if pc == 0x807F0000:
                    assert selected == 0x80690000 and load(selected + 0x198) == 0x8021A890
                    assert load(selected + 12) == 1 and state[8] == 0
                else:
                    assert selected == 0x80680000 and state[8] == 1
            else:
                assert state[-1] == ((msr | 2) if same_owner else (msr & ~0x2000) | 2)
    records.append({'input': case, 'state': state, 'events': list(events), 'memoryHex': memory})
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {'result': f'ORIGINAL_SELECT_THREAD_NATIVE_PPC{len(cases)}_{"DEFAULT_CALLBACK" if args.default_callback else "FRONTIER"}_CASES_PASS', 'records': records,
          'hostSha256': sha(host), 'includedHostSha256': sha(Path('experiments/wii-static-recomp/ios_open_host.cpp')),
          'scriptSha256': sha(Path(__file__)), 'dolSha256': sha(dol_path), 'analysisSha256': sha(base_output / 'analysis.json'),
          'generatedSha256': sha(base_output / 'selected.cpp'), 'executableSha256': sha(exe),
          'limits': ['Prepared current/ready TCBs and nonzero ready-mask; current-context getter/save are explicit services.',
                     'Stops before switch callback/context loading, no actual CPU switch or original OSContext save.',
                     'Idle wait, non-default callbacks, context mismatch/save-return1, IRQ delivery and malformed queues unverified.',
                     'No original transport/kernel integration or ordinary boot activation.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
if args.default_callback:
    report['callbackSourceSha256'] = sha(Path(extra_sources[0]))
    report['initialDolCallback'] = '0x8021a1a0'
    report['noSwitchReturns'] = sum(record['state'][0] == 0x807F0000 for record in records)
    report['contextSettingBoundaries'] = sum(record['state'][0] == 0x80213830 for record in records)
    if not args.set_context:
        assert (report['noSwitchReturns'], report['contextSettingBoundaries']) == (120, 96)
    report['limits'][1] = 'Original default BLR callback executes; stop before OSSetCurrentContext/OSLoadContext, no actual CPU switch.'
    report['limits'].append('Initial DOL callback pointer verified; later runtime overrides unverified.')
    (output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
if args.set_context:
    report['result'] = 'ORIGINAL_SELECTOR_GETTER_SET_CONTEXT_1296_CASES_PASS'
    report['contextLoadingBoundaries'] = sum(record['state'][0] == 0x80213920 for record in records)
    if not args.context_transfer:
        assert (report['noSwitchReturns'], report['contextLoadingBoundaries']) == (720, 576)
    report['contextAnalysisSha256'] = sha(Path('work/private-game/static-recomp/ios-set-context/analysis.json'))
    report['contextSourceSha256'] = sha(Path(extra_sources[2]))
    report['getterSourceSha256'] = sha(Path(extra_sources[1]))
    report['limits'] = ['Prepared queues/FPU-owner/MSR values; original getter/default callback/context setter execute.',
                        'Context save remains provided return0; stops before original OSLoadContext.',
                        'No actual context transfer/IRQ/idle wait or physical Wii trace; isync hardware visibility unverified.',
                        'No transport integration, later callback override or ordinary boot activation.']
    (output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
if args.context_transfer:
    report['result'] = 'ORIGINAL_SELECTOR_CONTEXT_TRANSFER_1296_CASES_PASS'
    report['preparedNextEntries'] = sum(record['state'][0] == 0x807F4000 for record in records)
    report['selfResumptions'] = sum(record['state'][0] == 0x807F0000 and record['state'][38] == 0x8021A890 for record in records)
    assert (report['noSwitchReturns'], report['preparedNextEntries'], report['selfResumptions']) == (756, 540, 36)
    report['saveSourceSha256'] = sha(Path(extra_sources[3]))
    report['loadSourceSha256'] = sha(Path(extra_sources[4]))
    report['saveAnalysisSha256'] = sha(Path('work/private-game/static-recomp/ios-save-context/analysis.json'))
    report['loadAnalysisSha256'] = sha(Path('work/private-game/static-recomp/ios-load-context/analysis.json'))
    report['limits'] = ['Original selector/getter/default callback/context save/set/load execute with prepared TCBs, flags0 and EE0.',
                        'Native driver dispatches resumed selector PC8021A890; original continuation executes through return.',
                        'New thread stops before prepared entry marker; idle/IRQ/FPU lifecycle/wakeup coupling/full boot unverified.',
                        'No physical Wii trace; initial D4/E4 equal; later callback overrides and malformed queues unverified.']
    (output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
stage = 'original context-transfer' if args.context_transfer else 'original getter/set-context' if args.set_context else 'original default-callback' if args.default_callback else 'selection-frontier'
limit = 'EE1/idle/wakeup/full boot unverified' if args.context_transfer else 'real context switch unverified'
print(f'PASS original SelectThread native/PPC: {len(cases)} {stage} cases; {limit}')
