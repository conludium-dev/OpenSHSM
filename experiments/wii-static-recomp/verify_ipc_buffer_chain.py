"""Execute the original IPC buffer chain with explicit synthetic loader inputs."""
from pathlib import Path
import hashlib
import json
import platform
import re
import struct
import sys

assert platform.machine() == 'x86_64', 'Use the verified Rosetta PPC Unicorn runtime'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
import unicorn
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

private = Path('work/private-game/static-recomp')
output = private / 'ipc-sdk-roots'
output.mkdir(exist_ok=True)
assembly_path = private / 'dtk-output/asm/auto_03_802045CC_text.s'
assembly = assembly_path.read_text()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
sections = [(header[i], header[18 + i], header[36 + i]) for i in range(18) if header[36 + i]]
names = ['__OSInitIPCBuffer', 'fn_8021C680', 'fn_8021C690', 'IPCInit',
         'IPCGetBufferHi', 'IPCGetBufferLo', 'IPCSetBufferLo']
roots = {}
for name in names:
    match = re.search(rf'# \.text:0x[0-9A-F]+ \| 0x([0-9A-F]+) \| size: 0x([0-9A-F]+)\n\.fn {name}, (?:global|local)\n(.*?)\.endfn {name}', assembly, re.S)
    assert match, name
    address, size = (int(value, 16) for value in match.groups()[:2])
    rows = re.findall(r'/\* ([0-9A-F]{8}) [0-9A-F]{8}  ([0-9A-F ]+) \*/', match.group(3))
    assert len(rows) * 4 == size
    body = b''
    for index, (pc, hexadecimal) in enumerate(rows):
        pc = int(pc, 16)
        assert pc == address + index * 4
        offset, base, _ = next(row for row in sections if row[1] <= pc < row[1] + row[2])
        word = bytes.fromhex(hexadecimal)
        assert word == dol[offset + pc - base:offset + pc - base + 4]
        body += word
    roots[name] = {'address': address, 'size': size, 'sha256': hashlib.sha256(body).hexdigest()}

uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
for offset, address, size in sections:
    uc.mem_write(address, dol[offset:offset + size])
registers = [getattr(ppc, f'UC_PPC_REG_{i}') for i in range(32)]
sentinel = 0x807F0000
trace = []


def observe(machine, address, size, data):
    assert any(row['address'] <= address < row['address'] + row['size'] for row in roots.values()), hex(address)
    trace.append(address)


uc.hook_add(UC_HOOK_CODE, observe)


def store(address, value):
    uc.mem_write(address, struct.pack('>I', value))


def load(address):
    return struct.unpack('>I', uc.mem_read(address, 4))[0]


def execute(name, argument=0):
    for i, register in enumerate(registers):
        uc.reg_write(register, 0x12340000 + i)
    uc.reg_write(registers[1], 0x80700000)
    uc.reg_write(registers[13], 0x8052E720)
    uc.reg_write(registers[3], argument)
    uc.reg_write(ppc.UC_PPC_REG_LR, sentinel)
    uc.reg_write(ppc.UC_PPC_REG_CR, 0xA5A5A5A5)
    trace.clear()
    uc.emu_start(roots[name]['address'], sentinel, count=100)
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == sentinel, name
    assert uc.reg_read(registers[1]) == 0x80700000 and uc.reg_read(registers[13]) == 0x8052E720
    return uc.reg_read(registers[3]), list(trace)


pairs = [(0x80600000, 0x80604000), (0x817FE000, 0x81800000),
         (0x93E00000, 0x94000000), (0x90000000, 0x90001000),
         (0, 0), (0xFFFFFFFF, 0), (0x80604000, 0x80600000), (0x80600001, 0x80601001)]
records = []
invocations = 0
for low, high in pairs:
    for initialized in (0, 1):
        store(0x80003130, low)
        store(0x80003134, high)
        _, os_trace = execute('__OSInitIPCBuffer')
        assert load(0x80528A38) == low and load(0x8052AB10) == high
        assert execute('fn_8021C690')[0] == low and execute('fn_8021C680')[0] == high
        uc.mem_write(0x8052AFC0, bytes([initialized]))
        store(0x8052AFC4, 0x80608000)
        store(0x8052AFC8, 0x8060C000)
        store(0x8052AFCC, 0x11111111)
        store(0x8052AFD0, 0x22222222)
        _, init_trace = execute('IPCInit')
        expected_low, expected_high = (0x80608000, 0x8060C000) if initialized else (low, high)
        assert execute('IPCGetBufferLo')[0] == expected_low
        assert execute('IPCGetBufferHi')[0] == expected_high
        assert bytes(uc.mem_read(0x8052AFC0, 1)) == b'\x01'
        assert load(0x8052AFCC) == (0x11111111 if initialized else low)
        assert load(0x8052AFD0) == (0x22222222 if initialized else high)
        advanced = (expected_low + 0x1000) & 0xFFFFFFFF
        execute('IPCSetBufferLo', advanced)
        store(0x80528A38, 0xDEADBEEF)
        store(0x8052AB10, 0xAABBCCDD)
        _, repeat_trace = execute('IPCInit')
        assert load(0x8052AFC4) == advanced and load(0x8052AFC8) == expected_high
        invocations += 8
        records.append({'loaderLow': hex(low), 'loaderHigh': hex(high), 'priorInitialized': initialized,
                        'clientLow': hex(expected_low), 'clientHigh': hex(expected_high),
                        'advancedLowRetained': hex(advanced), 'osTrace': [hex(pc) for pc in os_trace],
                        'initTrace': [hex(pc) for pc in init_trace], 'repeatTrace': [hex(pc) for pc in repeat_trace]})

vendor_main = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/core/main.cpp')
vendor_text = vendor_main.read_text()
seeds = {int(address, 16): int(value, 16) for address, value in
         re.findall(r'poke_global\((0x[0-9a-fA-F]+), (0x[0-9a-fA-F]+)\);', vendor_text)}
assert seeds[0x80003130] == 0x93E00000 and seeds[0x80003134] == 0x94000000
report = {'result': 'ORIGINAL_IPC_BUFFER_CHAIN_16_FIXTURES_128_INVOCATIONS_PASS',
          'records': records, 'roots': roots, 'invocations': invocations,
          'dolSha256': hashlib.sha256(dol).hexdigest(),
          'assemblySha256': hashlib.sha256(assembly_path.read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'unicornVersion': unicorn.__version__,
          'vendorMainSha256': hashlib.sha256(vendor_main.read_bytes()).hexdigest(),
          'pcAdaptation': {'vendorLoaderLow': hex(seeds[0x80003130]), 'vendorLoaderHigh': hex(seeds[0x80003134]),
                           'classification': 'Pinned NWiiRuntime boot seed, not original SHSM measurement; excluded by MEM1 parser.'},
          'originalBehavior': ['OS initialization copies loader words 80003130/34 into SDA buffer bounds.',
                               'First IPCInit copies OS bounds; subsequent calls retain client bounds.',
                               'IPCSetBufferLo replaces the client low bound without validation.'],
          'limits': ['Synthetic loader inputs, including MEM2/invalid bounds; not measured full-game loader state.',
                     'Unicorn executes original integer PPC; no physical Wii or native recomp comparison.',
                     'No allocation, cache flush, MMIO, IRQ, thread, IOS sender execution or boot activation.',
                     'Current native OPEN parser supports only its bounded MEM1 fixture; real allocation region remains unverified.']}
(output / 'buffer-chain.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS original IPC buffer chain: {len(records)} fixtures, {invocations} calls; loader region still unverified')
