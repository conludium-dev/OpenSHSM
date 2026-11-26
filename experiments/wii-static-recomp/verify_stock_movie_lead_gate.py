"""Owned DOL integer lead gate oracle; correlate snapshots without claiming a full live branch trace."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import struct
import sys

assert platform.machine() == 'x86_64', 'Use existing isolated x64 Unicorn setup'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'movie-lead-gate'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
def read(address, size):
    i = next(i for i in range(18) if header[18 + i] <= address and address + size <= header[18 + i] + header[36 + i])
    offset = header[i] + address - header[18 + i]
    return dol[offset:offset + size]

facts = [(0x8009B6E4, 0x881E00A7), (0x8009B6EC, 0x41820034),
    (0x8009B6F0, 0x807E00F4), (0x8009B6F4, 0x801E00F0),
    (0x8009B6F8, 0x7C030050), (0x8009B6FC, 0x2C000001), (0x8009B700, 0x4181002C),
    (0x8009B268, 0x901C00F4), (0x8009BC8C, 0x901E00F4), (0x8009BE3C, 0x901F00F4)]
for address, expected in facts:
    assert struct.unpack('>I', read(address, 4))[0] == expected
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
uc.mem_write(0x8009B6DC, read(0x8009B6DC, 0x54))
stops = []
trail = []
def stop(uc, address, size, user_data):
    trail.append(address)
    if address in (0x8009B704, 0x8009B720, 0x8009B72C):
        stops.append(address)
        uc.emu_stop()
uc.hook_add(UC_HOOK_CODE, stop)
values = [0, 1, 2, 3, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]
cases = []
for flag, f0, f4 in itertools.product([0, 1, 2, 255], values, values):
    uc.mem_write(0x8046BBE7, bytes([flag]))
    uc.mem_write(0x8046BC30, struct.pack('>II', f0, f4))
    uc.reg_write(ppc.UC_PPC_REG_28, 0xFFFFFFFF)
    uc.reg_write(ppc.UC_PPC_REG_CR, 0xAAAAAAAA)
    stops.clear()
    trail.clear()
    try:
        uc.emu_start(0x8009B6DC, 0x8009B730, count=32)
    except Exception as error:
        raise AssertionError((flag, f0, f4, hex(uc.reg_read(ppc.UC_PPC_REG_PC)),
            [hex(address) for address in trail], str(error))) from error
    assert len(stops) == 1
    delta = (f0 - f4) & 0xFFFFFFFF
    signed_delta = delta if delta < 0x80000000 else delta - 0x100000000
    expected_pc = 0x8009B720 if flag == 0 else 0x8009B72C if signed_delta > 1 else 0x8009B704
    expected_candidate = 0xFFFFFFFF
    actual_candidate = uc.reg_read(ppc.UC_PPC_REG_28)
    assert stops[0] == expected_pc and actual_candidate == expected_candidate
    cases.append({'flagA7': flag, 'f0': f0, 'f4': f4, 'signedDifference': signed_delta,
        'stopPc': f'{stops[0]:08X}', 'candidate': f'{actual_candidate:08X}',
        'outcome': 'eligible-direct-poll' if flag == 0 else 'lead-block' if signed_delta > 1 else 'eligible-poll'})
capture = root / 'window-movie-update-update180-thp-movie-update.jsonl'
rows = [json.loads(line) for line in capture.read_text().splitlines()]
selected = [row for row in rows if row['pc'] == 0x8009B72C]
correlation = []
for row in selected:
    flag = bytes.fromhex(row['stateA0Hex'])[7]
    f0, f4 = struct.unpack('>II', bytes.fromhex(row['stateF0Hex'])[:8])
    delta = (f0 - f4) & 0xFFFFFFFF
    delta = delta if delta < 0x80000000 else delta - 0x100000000
    if flag != 0 and delta > 1 and row['candidate'] == 0xFFFFFFFF:
        correlation.append({'serial': row['serial'], 'observedHit': row['hits'], 'flagA7': flag,
            'f0': f0, 'f4': f4, 'candidate': 'FFFFFFFF'})
assert 0 < len(correlation) <= len(selected)
report = {'result': 'ORIGINAL_MOVIE_LEAD_GATE_FRAGMENT_PASS', 'cases': len(cases), 'caseResults': cases,
    'dolSha256': sha(dol_path), 'scriptSha256': sha(Path(__file__)),
    'fragmentSha256': hashlib.sha256(read(0x8009B6DC, 0x50)).hexdigest(),
    'instructionFacts': [{'address': f'{address:08X}', 'opcode': f'{opcode:08X}'} for address, opcode in facts],
    'captureSha256': sha(capture), 'conditionalSnapshotMatches': correlation,
    'unexplainedSentinelRows': [row['serial'] for row in selected if row['candidate'] == 0xFFFFFFFF
        and row['serial'] not in {item['serial'] for item in correlation}],
    'limits': ['Original integer control-flow fragment only, stopped BEFORE eligible queue call; no whole movie function or SDK execution.',
        'Snapshot correlation is a conditional reconstruction, not a live taken-branch/IRQ activation trace.',
        'F4 source producer8009BBF0 increments atBC8C/BE3C; its callback reachability and subsystem identity require separate evidence.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], len(cases), 'original PPC cases;', len(correlation), 'conditional live snapshot matches')
