"""Check original IRQ-priority evidence, actual host selection and bounded boot separately."""
import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
args = parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-transport-irq-order'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
source = (output / 'ios.cpp').read_text()
before = (root / 'window-transport-observe/ios.cpp').read_text()
finish = '              else if (active_ints & 0x00000400) { os_intr = 19; bit_to_clear = 0x00000400; } '
token = '              else if (active_ints & 0x00000200) { os_intr = 18; bit_to_clear = 0x00000200; } '
assert before.count(finish + '\n' + token) == 1
assert before.replace(finish + '\n' + token, token + '\n' + finish) == source
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])

def word(address):
    section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    offset = header[section] + address - header[18 + section]
    return struct.unpack_from('>I', dol, offset)[0]

assert word(0x80217BBC) == 0x7C600039
assert word(0x80217BC4) == 0x7C000034
groups = [word(0x8042CF98 + i * 4) for i in range(12)]
assert groups == [0x100, 0x40, 0xF8000000, 0x200, 0x80, 0x10, 0x3000, 0x20,
    0x03FF8C00, 0x04000000, 0x4000, 0xFFFFFFFF]
cases = []
for selected in range(8):
    active = sum(bit for i, bit in enumerate((0x200, 0x400, 0x800)) if selected & (1 << i))
    os_mask = sum(1 << (31 - event) for bit, event in ((0x200, 18), (0x400, 19), (0x800, 17)) if active & bit)
    matched = next((os_mask & group for group in groups if os_mask & group), 0)
    expected = 32 - matched.bit_length() if matched else -1
    cases.append((active, expected))
branch = re.search(r'else if \(active_ints & 0x00000200\).*?\n.*?0x00000400.*?\n.*?0x00000800.*?\n', source)[0]
branch = branch.replace('else if', 'if', 1)
fixture = '#include <cstdint>\nint choose(uint32_t active_ints) {\nint os_intr = -1; uint32_t bit_to_clear = 0;\n' + branch + '\nreturn os_intr;\n}\nint main() {\n'
fixture += '\n'.join(f'if (choose({active}) != {expected}) return {i + 1};' for i, (active, expected) in enumerate(cases))
fixture += '\nreturn 0;\n}\n'
test_source = output / 'irq-selection-contract.cpp'
test_source.write_text(fixture)
test = output / 'irq-selection-contract'
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++17',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
    str(test_source), '-o', str(test)], check=True, capture_output=True, timeout=30)
subprocess.run([str(test)], check=True, capture_output=True, timeout=5)
build = json.loads((output / 'build.json').read_text())
assert build['sourceSha256'] == sha(output / 'ios.cpp') and build['tokenBeforeFinish']
assert len(build['retainedObjects']) == 77
for name, expected in build['retainedObjects'].items():
    path = Path(name)
    assert sha(path if path.is_absolute() else root / 'export/build' / path) == expected
for member, expected in build['retainedRuntimeMembers'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(output / 'libnwiiruntime.a'), member])
    assert hashlib.sha256(data).hexdigest() == expected
label = 'window-transport-irq-order-headless-gx-windowed-' + args.tag
run = json.loads((root / (label + '-result.json')).read_text())
assert run['executableSha256'] == build['executableSha256'] == sha(output / 'OpenSHSMStockTransportIRQOrder')
assert run['logSha256'] == sha(root / (label + '.log')) and run['originalDolSha256'] == sha(dol_path)
log = (root / (label + '.log')).read_text(errors='replace')
report = {
    'result': 'IRQ_PAIR_PROVENANCE_AND_SELECTION_PASS', 'actualCompiledSelectionCases': cases,
    'dolSha256': sha(dol_path), 'priorityTableAddress': '0x8042CF98', 'priorityGroups': groups,
    'sourceSha256': sha(output / 'ios.cpp'), 'runSha256': sha(root / (label + '-result.json')),
    'terminalReturncode': run['terminalReturncode'], 'gpuHangReported': 'GPU Hang' in log,
    'limits': ['Only CP/PE three-line host selection is compiled in the component fixture; no original interrupt execution oracle.',
        'Only PE token/finish relative order changed; full original OS dispatch, scheduler and IRQ timing remain unverified.',
        'Component PASS does not establish menu, successful boot, render correctness or gameplay.']
}
(output / ('audit-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print('PASS 8 actual host-selection cases against own DOL priority table; boot GPU Hang:', report['gpuHangReported'])
