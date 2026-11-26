"""Own DOL channel-state query candidate; native/original finite comparison, not connected-input integration."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import struct
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--oracle', action='store_true')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'wpad-probe-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if not args.oracle:
    build_path = root / 'window-legacy-context/build.json'
    build = json.loads(build_path.read_text())
    command = list(build['linkCommand'])
    full = root / 'window-quantization'
    command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
    source = Path('experiments/wii-static-recomp/stock_wpad_probe_contract.cpp').resolve()
    arguments = next(row['arguments'] for row in json.loads((full / 'build.json').read_text())['compiled']
        if row['source'] == 'main_output.cpp')
    obj = output / 'probe.cpp.o'
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=60)
    (output / 'compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    command.insert(1, str(obj))
    exe = output / 'wpad-probe-contract'
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    (output / 'probe.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and result.stdout.count('PROBE ') == 192, result.stdout + result.stderr
    (output / 'native.json').write_text(json.dumps({'result': 'NATIVE_WPAD_QUERY_CANDIDATE_COMPLETE',
        'sourceSha256': sha(source), 'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'),
        'baseBuildSha256': sha(build_path), 'linkCommand': command, 'recipeSha256': sha(Path(__file__)),
        'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
            and Path(arg).suffix in ('.o', '.a') and arg != str(obj)}}, indent=2) + '\n')
    print('NATIVE_WPAD_QUERY_CANDIDATE_COMPLETE 192')
    sys.exit(0)
assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
from unicorn import ppc_const as ppc
native_path = output / 'native.json'
native = json.loads(native_path.read_text())
assert native['recipeSha256'] == sha(Path(__file__)) and sha(output / 'probe.log') == native['logSha256']
for path, expected in native['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
def read(address, size):
    section = next(i for i in range(18) if header[18 + i] <= address
        and address + size <= header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    return dol[offset:offset + size]
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
fragments = [(0x80280AC0, 140), (0x802174E0, 20), (0x80217520, 36)]
for address, size in fragments:
    uc.mem_write(address, read(address, size))
cases = []
for line in (output / 'probe.log').read_text().splitlines():
    if not line.startswith('PROBE '):
        continue
    channel, state, type_id, ready, has_output, native_result, native_type = map(int, line.split()[1:])
    block = 0x80540000 + channel * 0x1000
    for address, value in [(0x804F13F0 + channel * 4, block), (block + 0x8BC, state),
        (block + 0x8DC, ready), (0x80560000, 0xCAFEBABE)]:
        uc.mem_write(address, struct.pack('>I', value))
    uc.mem_write(block + 0x8C1, bytes([type_id]))
    for register, value in [(ppc.UC_PPC_REG_1, 0x80570000), (ppc.UC_PPC_REG_3, channel),
        (ppc.UC_PPC_REG_4, 0x80560000 if has_output else 0), (ppc.UC_PPC_REG_LR, 0x8009BB80), (ppc.UC_PPC_REG_MSR, 0)]:
        uc.reg_write(register, value)
    uc.emu_start(0x80280AC0, 0x8009BB80, count=128)
    actual = uc.reg_read(ppc.UC_PPC_REG_3)
    actual_type = struct.unpack('>I', uc.mem_read(0x80560000, 4))[0]
    expected = 0xFFFFFFFF if state == 0xFFFFFFFF or type_id == 0xFD else 0xFFFFFFFE if ready == 0 else state
    assert actual == native_result == expected and actual_type == native_type == (type_id if has_output else 0xCAFEBABE)
    assert uc.reg_read(ppc.UC_PPC_REG_PC) == 0x8009BB80 and uc.reg_read(ppc.UC_PPC_REG_1) == 0x80570000
    cases.append({'channel': channel, 'rawState': state, 'type': type_id, 'ready': ready,
        'hasOutput': has_output, 'originalResult': actual, 'nativeResult': native_result, 'typeOutput': actual_type})
(output / 'original-comparison.json').write_text(json.dumps({'result': 'ORIGINAL_NATIVE_WPAD_QUERY_COMPARISON_PASS',
    'cases': cases, 'dolSha256': sha(dol_path), 'nativeReportSha256': sha(native_path), 'recipeSha256': sha(Path(__file__)),
    'fragments': {f'{a:08X}': hashlib.sha256(read(a, size)).hexdigest() for a, size in fragments},
    'facts': {'queryAddress': '80280AC0', 'channelTable': '804F13F0', 'rawStateOffset': '8BC',
        'typeOffset': '8C1', 'readyOffset': '8DC', 'gameCaller': '8018E354', 'nextReadCandidate': '8027AAC0',
        'samplingCallbackCandidate': '80280B50', 'connectCallbackCandidate': '80280BE0'},
    'limits': ['Full query plus original interrupt disable/restore in software750CL; supplied channel-control blocks, no physical Bluetooth.',
        'WPADProbe semantic name inferred from SDK strings/caller shape/contract, not original symbol table.',
        'Valid channels0..3 only; no invalid-channel acceptance claimed.',
        'KPAD read/buffer format/connect lifecycle and actual warning predicate remain unverified; no adapter integration.']}, indent=2) + '\n')
print('ORIGINAL_NATIVE_WPAD_QUERY_COMPARISON_PASS', len(cases))
