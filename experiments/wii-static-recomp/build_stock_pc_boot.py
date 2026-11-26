"""PC boot adaptation on the existing startup selection, not an input/readiness bypass."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-pc-boot'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-audio-refill/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
command = list(parent['linkCommand'])
original_obj = next(Path(arg) for arg in command if Path(arg).name == 'output_18.cpp.o')
original = original_obj.with_suffix('')
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
def read(address, size):
    section = next(i for i in range(18) if layout[18 + i] <= address
        and address + size <= layout[18 + i] + layout[36 + i])
    offset = layout[section] + address - layout[18 + section]
    return dol[offset:offset + size]

asm_path = root.parent / 'dtk-output/asm/auto_03_8010016C_text.s'
body = asm_path.read_text().split('.fn fn_801003E4,')[1].split('.endfn fn_801003E4')[0]
words = re.findall(r'/\* ([0-9A-F]{8}) [0-9A-F]{8}  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/', body)
assert len(words) == 233
for address, word in words:
    assert read(int(address, 16), 4) == bytes.fromhex(word)
assert read(0x80100568, 4).hex() == '800f0010'
records = []
for index in range(12):
    entry = read(0x803F2418 + index * 32, 32)
    kind, name = struct.unpack('>2I', entry[:8])
    label = read(name, 32).split(b'\0')[0].decode() if name and kind == 1 else None
    records.append({'index': index, 'kind': kind, 'name': label, 'sha256': hashlib.sha256(entry).hexdigest()})
assert [row['name'] for row in records[:4]] == ['UI_Warning1', 'UI_Warning2'] * 2
assert records[5]['name'] == 'UI_Nunchuk' and records[6]['kind'] == 6
assert records[7]['name'] == 'UI_Legal' and records[8]['name'] == 'UI_PsychologyWarning'
before = 'loc_80100568: ;\n'
after = before + '    openshsm::experiment::skip_pc_boot_notices(ctx);\n'
text = original.read_text()
count = text.count(before)
assert count == 9
source, obj = output / 'output_18.cpp', output / 'output_18.cpp.o'
source.write_text('#include "stock_pc_boot_notices.h"\n' + text.replace(before, after))
assert source.read_text().removeprefix('#include "stock_pc_boot_notices.h"\n').replace(after, before) == text
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'output_18.cpp')
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command[command.index(str(original_obj))] = str(obj)
exe = output / 'OpenSHSMStockPCBoot'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({'result': 'PC_BOOT_BUILT_LIVE_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'originalPath': str(original), 'originalSha256': sha(original),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'executableSha256': sha(exe),
    'headerSha256': sha(public / 'stock_pc_boot_notices.h'), 'recipeSha256': sha(Path(__file__)),
    'dolSha256': sha(dol_path), 'dtkSha256': sha(asm_path), 'originalStartupWords': len(words),
    'records': records, 'hookCopies': count, 'linkCommand': command, 'arguments': arguments,
    'retainedInputs': {str((Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()):
        sha((Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve())
        for arg in command if Path(arg).suffix in ('.o', '.a') and arg != str(obj)},
    'limits': ['Explicit opt-in PC adaptation skips indices0..3 and5 at original selection before UI construction.',
        'Original cleanup, index4 barrier, index6 action, legal/psychology notices, input and runtime retained.',
        'Not original Wii behavior; original DOL/assets unchanged, physical controllers unverified.']}, indent=2) + '\n')
print('PC_BOOT_BUILT_LIVE_UNVERIFIED', count)
