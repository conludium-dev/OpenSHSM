"""Verify actual linked SDK save/load for populated finite contexts, not hardware oracle."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'fpu-populated-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-scheduler-observe/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
guest = next(Path(arg) for arg in command if Path(arg).name == 'output_38.cpp.o').with_suffix('')
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f', 'Unsupported Wii DOL'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
text = guest.read_text()
sites = []
for entry in (0x802135C0, 0x802136F0):
    start = text.index(f'void func_{entry:08X}(')
    end = text.index('\nvoid func_', start + 1)
    for address, opcode in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', text[start:end]):
        address, opcode = int(address, 16), int(opcode, 16)
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        offset = layout[section] + address - layout[18 + section]
        assert struct.unpack_from('>I', dol, offset)[0] == opcode
        sites.append({'address': hex(address), 'opcode': hex(opcode)})
record = json.loads((root / 'window-fp-guard/output_38.cpp.record.json').read_text())
source, obj = public / 'stock_fpu_populated_probe.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'populated-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
assert 'POPULATED_NATIVE_FPU_SAVE_LOAD_PASS 12' in result.stdout
(output / 'verification.json').write_text(json.dumps({'result': 'POPULATED_NATIVE_FPU_SAVE_LOAD_PASS12',
    'baseBuildSha256': sha(base_path), 'dolSha256': sha(dol_path), 'guestSourceSha256': sha(guest), 'instructionSites': sites,
    'probeSourceSha256': sha(source), 'executableSha256': sha(exe), 'logSha256': sha(output / 'probe.log'),
    'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Actual linked SaveFPU/LoadFPU functions,all original instruction comments checked against ownDOL.',
        '12finite cases/GQR0=0/paired enabled-disabled/6FPSCR states/32primary64 and secondary-float32 lanes/empty gate.',
        'Fixture starts FP-active/EEdisabled,does not execute original unavailable owner-switch lifecycle or interrupted video.',
        'Raw mffs upper payload and NaN/subnormal/unsupported profiles not independently verified; no complete Wii hardware/paired oracle.',
        'No runtime/source behavior changes or visual/performance acceptance.']}, indent=2) + '\n')
print('POPULATED_NATIVE_FPU_SAVE_LOAD_PASS12', len(sites))
