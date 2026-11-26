"""Execute retained generated SDK functions; compare original DOL-derived register operations."""
from pathlib import Path
import hashlib
import json
import os
import re
import struct
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root.parent / 'stock-adma-sdk/native'
output.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = root / 'window-debug-overlay/build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
guest_record_path = root / 'window-fp-guard/output_39.cpp.record.json'
guest_record = json.loads(guest_record_path.read_text())
guest_source = root / 'window-fp-guard/output_39.cpp'
assert sha(guest_source) == guest_record['sourceSha256']
assert sha(Path(guest_record['object'])) == guest_record['objectSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
guest_text = guest_source.read_text()
for address, count in [(0x8022CAB0, 31), (0x8022CB30, 5), (0x8022CB50, 5), (0x8022CB70, 4)]:
    body = guest_text.split(f'void func_{address:08X}(CPUContext& ctx) {{')[1].split('\nvoid func_')[0]
    words = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body)
    assert len(words) == count
    for location, word in words:
        pc = int(location, 16)
        section = next(i for i in range(18) if layout[18 + i] <= pc < layout[18 + i] + layout[36 + i])
        offset = layout[section] + pc - layout[18 + section]
        assert struct.unpack_from('>I', dol, offset)[0] == int(word, 16)
source, obj = public / 'stock_adma_sdk_probe.cpp', output / 'probe.cpp.o'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
assert compiled.returncode == 0, compiled.stderr[-3000:]
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'sdk-probe'
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(linked.stdout + linked.stderr)
assert linked.returncode == 0, linked.stderr[-2500:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
log = output / 'probe.log'
log.write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'OWN_WII_ADMA_SDK_NATIVE_MMIO_PASS cases=12 calls=60' in result.stdout, (result.returncode, result.stdout, result.stderr)
ghidra_path = root.parent / 'stock-adma-sdk/ghidra/verification.json'
ghidra = json.loads(ghidra_path.read_text())
assert ghidra['result'] == 'OWN_WII_ADMA_SDK_DTK_GHIDRA141_WORDS564_BYTES'
functions_header = root / 'export/functions.h'
(output / 'verification.json').write_text(json.dumps({
    'result': 'OWN_WII_ADMA_SDK_NATIVE_MMIO_PASS12_CASES60_CALLS', 'buildSha256': sha(build_path),
    'sourceSha256': sha(source), 'executableSha256': sha(exe), 'logSha256': sha(log),
    'ghidraProofSha256': sha(ghidra_path), 'verifierSha256': sha(Path(__file__).resolve()),
    'functionsHeaderSha256': sha(functions_header), 'linkCommand': command,
    'guestRecordSha256': sha(guest_record_path), 'guestSourceSha256': sha(guest_source),
    'originalDolSha256': sha(dol_path),
    'retainedLinkInputs': build['retainedLinkInputs'],
    'limits': ['Retained original compiled SDK functions/setup-start-stop-count executed through actual MMIO.',
        'Register expectations derived from owned DOL/DTK/Ghidra, no independent original runtime/hardware comparison.',
        'DMA countdown still returns legacy zero; no chunk/latching/rate/PCM device fix claimed.']}, indent=2) + '\n')
print('OWN_WII_ADMA_SDK_NATIVE_MMIO_PASS12_CASES60_CALLS')
