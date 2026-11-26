"""Check reversible patch, retained link inputs and bounded adaptation fixtures."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-pc-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in build['retainedInputs'].items():
    assert sha(Path(path)) == digest
assert sha(Path(build['originalPath'])) == build['originalSha256']
assert sha(output / 'output_18.cpp') == build['sourceSha256']
assert sha(output / 'output_18.cpp.o') == build['objectSha256']
assert sha(output / 'OpenSHSMStockPCBoot') == build['executableSha256']
assert sha(public / 'stock_pc_boot_notices.h') == build['headerSha256']
patched = (output / 'output_18.cpp').read_text()
restored = patched.removeprefix('#include "stock_pc_boot_notices.h"\n').replace(
    'loc_80100568: ;\n    openshsm::experiment::skip_pc_boot_notices(ctx);\n', 'loc_80100568: ;\n')
assert restored == Path(build['originalPath']).read_text()
source, exe = public / 'stock_pc_boot_probe.cpp', output / 'boot-probe'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk', '-I', str(public),
    str(source), '-o', str(exe)], capture_output=True, text=True, timeout=60)
assert result.returncode == 0, result.stderr
logs = []
for value in ['', '0', '1', '01', 'true']:
    env = dict(os.environ, NWII_SKIP_BOOT_NOTICES=value)
    result = subprocess.run([str(exe), value], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and 'PC_BOOT_ADAPTER_PASS 19' in result.stdout, result.stderr
    logs.append(result.stdout + result.stderr)
(output / 'probe.log').write_text(''.join(logs))
(output / 'verification.json').write_text(json.dumps({'result': 'PC_BOOT_ADAPTER95_CASES_SOURCE_RETENTION_PASS',
    'buildSha256': sha(build_path), 'probeSha256': sha(source), 'executableSha256': sha(exe),
    'logSha256': sha(output / 'probe.log'), 'verifierSha256': sha(Path(__file__)),
    'limits': ['95 synthetic adapter cases, not original full boot or physical Wii equivalence.',
        'Full original startup233words checked against DOL/DTK by builder; live rendering separate.']}, indent=2) + '\n')
print('PC_BOOT_ADAPTER95_CASES_SOURCE_RETENTION_PASS')
