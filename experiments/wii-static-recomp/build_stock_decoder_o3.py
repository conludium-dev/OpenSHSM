"""Recompile the identical verified decoder with O3, retaining numerical flags and the current runtime."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-decoder-o3'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'window-hid2-inline/build.json'
base = json.loads(base_path.read_text())
for path, digest in {**base['dependencies'], **base['retainedInputs']}.items():
    assert sha(Path(path)) == digest
source, obj, header = output / 'output_37.cpp', output / 'output_37.cpp.o', output / 'constant_fp_guard.h'
source.write_bytes((root / 'window-hid2-inline/output_37.cpp').read_bytes())
header.write_bytes((root / 'window-hid2-inline/constant_fp_guard.h').read_bytes())
arguments = list(base['arguments'])
assert arguments.count('-O2') == 1 and '-ffp-contract=off' in arguments and '-fwrapv' in arguments
assert not any('fast-math' in arg for arg in arguments)
arguments[arguments.index('-O2')] = '-O3'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-I', str(root / 'headless-psq-scale'), '-c', str(source), '-o', str(obj)],
    capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = list(base['linkCommand'])
command[command.index(str(root / 'window-hid2-inline/output_37.cpp.o'))] = str(obj)
exe = output / 'OpenSHSMStockDecoderO3'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
base.update(result='DECODER_O3_BUILT_DIFFERENTIAL_PERFORMANCE_UNVERIFIED', inlineBuildSha256=sha(base_path),
    sourceSha256=sha(source), objectSha256=sha(obj), executableSha256=sha(exe), arguments=arguments, linkCommand=command)
base['dependencies'] = {**base['dependencies'], str(Path(__file__).resolve()): sha(Path(__file__)),
    str(header): sha(header)}
base['limits'] += ['Identical source/header, O3only; fwrapv/no-strict-aliasing/ffp-contract-off retained, no fast-math.',
    'Performance/equivalence pending; neither inline nor O3 is promoted by construction.']
(output / 'build.json').write_text(json.dumps(base, indent=2) + '\n')
print('DECODER_O3_BUILT_DIFFERENTIAL_PERFORMANCE_UNVERIFIED')
