"""Add loss/flush accounting to existing converter/observer; one derived DSP object only."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_adma_accounting_patch import counted_output, counted_dsp

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-adma-accounting'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-adma-chunks/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
base_source = root / 'window-adma-chunks/hw_dsp.cpp'
assert sha(base_source) == next(row['sourceSha256'] for row in parent['compiled'] if Path(row['source']).name == 'hw_dsp.cpp')
source, obj = output / 'hw_dsp.cpp', output / 'hw_dsp.cpp.o'
source.write_text(counted_dsp(base_source.read_text()))
header = output / 'stock_adma_output.h'
header.write_text(counted_output((public / 'stock_adma_output.h').read_text()))
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'hw_dsp.cpp')
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
archive = output / 'libnwiiruntime.a'
base_archive = root / 'window-adma-chunks/libnwiiruntime.a'
assert sha(base_archive) == parent['archiveSha256']
archive.write_bytes(base_archive.read_bytes())
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
members = {}
for name, digest in parent['members'].items():
    actual = hashlib.sha256(subprocess.run(['/usr/bin/ar', 'p', str(archive), name], check=True, capture_output=True).stdout).hexdigest()
    members[name] = actual
    if name != 'hw_dsp.cpp.o':
        assert actual == digest
command = list(parent['linkCommand'])
command[command.index(str(base_archive))] = str(archive)
exe = output / 'OpenSHSMStockADMAAccounting'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'ADMA_ACCOUNTING_BUILT_EXECUTION_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'archiveSha256': sha(archive), 'members': members, 'linkCommand': command,
    'retainedLinkInputs': parent['retainedLinkInputs'],
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(),
        public / 'stock_adma_accounting_patch.py', public / 'stock_adma_accounting.h',
        public / 'stock_adma_output.h', header]},
    'limits': ['Converter count-only extension, same PCM/resampling/cap/ring/scheduling/main/all75guests.',
        'Observer replaces previous incorrect cap metrics; accepted-supplied=ring checked under existing mutex.',
        'TB snapshot published by CPU producer, never read GUI-side without ownership; not original game speed percent.']}, indent=2) + '\n')
print('ADMA_ACCOUNTING_BUILT_EXECUTION_UNVERIFIED')
