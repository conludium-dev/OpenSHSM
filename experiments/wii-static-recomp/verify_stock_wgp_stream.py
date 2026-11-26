"""Exercise actual WGP/MMIO/parser objects with capture enabled before retail probing."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
from stock_wgp_stream_patch import adapt

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
full, base, output = root / 'window-quantization', root / 'window-fp-guard', root / 'window-wgp-stream'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
parent = json.loads((full / 'build.json').read_text())
assert (output / 'gx.cpp').read_text() == adapt((full / 'gx.cpp').read_text())
assert sha(output / 'gx.cpp') == build['sourceSha256'] and sha(output / 'gx.cpp.o') == build['objectSha256']
assert sha(output / 'libnwiiruntime.a') == build['archiveSha256']
assert sha(base / 'build.json') == build['baseBuildSha256']
assert all(sha(Path(path)) == digest for path, digest in build['retainedLinkInputs'].items())
for member, digest in build['retainedRuntimeMembers'].items():
    for archive in (base / 'libnwiiruntime.a', output / 'libnwiiruntime.a'):
        assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])).hexdigest() == digest
source = Path('experiments/wii-static-recomp/stock_cp_transport_contract.cpp').resolve()
item = next(row for row in parent['compiled'] if row['source'] == 'gx.cpp')
obj = output / 'transport-contract.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *item['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'contract-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = list(build['linkCommand'])
entry = full / 'contract-entry.cpp.o'
main = str(full / 'main.cpp.o')
assert main in command and entry.exists()
command[command.index(main)] = str(entry)
command.insert(1, str(obj))
exe = output / 'transport-contract'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'contract-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
env = dict(os.environ)
env.update(NWII_GXDUMP=str(output / 'contract-stream.bin'), NWII_WGSEG=str(output / 'contract-segments.txt'),
    NWII_WGBURSTS=str(output / 'contract-bursts.bin'), NWII_CPSTREAM=str(output / 'contract-cp.bin'))
result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=20)
(output / 'contract-run.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
bursts = (output / 'contract-bursts.bin').read_bytes()
assert bursts and len(bursts) % 36 == 0
records = [{'address': int.from_bytes(bursts[i:i + 4], 'big'), 'payload': bursts[i + 4:i + 36].hex()}
    for i in range(0, len(bursts), 36)]
assert any(row['address'] < 0x01800000 for row in records)
assert any(0x10000000 <= row['address'] < 0x14000000 for row in records)
cp = (output / 'contract-cp.bin').read_bytes()
assert cp and len(cp) % 44 == 0
(output / 'contract.json').write_text(json.dumps({'result': 'CAPTURE_ENABLED_ACTUAL_TRANSPORT_CONTRACT_PASS',
    'output': result.stdout.strip(), 'bursts': records, 'command': command,
    'inputs': {str(path): sha(path) for path in [source, obj, entry, exe, output / 'gx.cpp',
        output / 'libnwiiruntime.a', Path('experiments/wii-static-recomp/stock_wgp_stream_patch.py'), Path(__file__)]},
    'limits': ['Actual existing runtime WGP/MMIO/parser components; no original Wii timing/retail execution or visual proof.',
        'Capture only; unchanged producer/decoder byte semantics checked by the retained transport contract.']}, indent=2) + '\n')
print('PASS capture-enabled actual transport contract;', len(records), 'MEM1/MEM2 bursts;', len(cp) // 44, 'actual parser inputs')
