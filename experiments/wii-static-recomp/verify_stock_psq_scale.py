"""Compare derived scale helpers against retained PSQ implementation on all64scales/types/W/banks."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-psq-scale'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = output / 'build.json'
base = json.loads(base_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
source, obj = public / 'stock_psq_scale_probe.cpp', output / 'probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'], '-I', str(output),
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
command = list(base['linkCommand'])
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'scale-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(output / 'probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
assert 'PSQ_SCALE_DIFFERENTIAL_PASS 49152' in result.stdout
(output / 'component-verification.json').write_text(json.dumps({'result': 'PSQ_SCALE_DIFFERENTIAL_PASS49152',
    'buildSha256': sha(base_path), 'probeSourceSha256': sha(source), 'executableSha256': sha(exe),
    'logSha256': sha(output / 'probe.log'), 'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['64signed scales x8types x2W x3RAMbanks x8finite/nonfinite samples xload/store; scale rawbits exact.',
        'Native load-lane/store-memory/refusal-message/partial write order differential, not new independent Wii hardware proof.',
        'Original dynamic FP/HID2/opcode guards remain unchanged outside these helpers; real complete-frame proof pending.']}, indent=2) + '\n')
print(result.stdout.strip())
