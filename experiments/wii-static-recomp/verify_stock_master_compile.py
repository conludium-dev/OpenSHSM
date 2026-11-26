"""Reproduce the current master recipe and compare executable text, not misleading historical labels."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'master-compile-verification'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = root / 'window-bounds-lookup/build.json'
build = json.loads(build_path.read_text())
builder = Path('experiments/wii-static-recomp/build_stock_bounds_lookup.py').resolve()
assert sha(builder) == build['dependencies'][str(builder)]
source = root / 'window-bounds-lookup/fixed.cpp'
original_obj = source.with_suffix('.cpp.o')
assert sha(source) == build['masterSourceSha256']
assert sha(original_obj) == build['masterObjectSha256']
sdk_record_path = root / 'window-sdk-enable-resume/build.json'
sdk_record = json.loads(sdk_record_path.read_text())
arguments = sdk_record.get('arguments')
flags_path = sdk_record_path
if arguments is None:
    flags_path = root / 'window-fp-guard/output_37.cpp.record.json'
    arguments = json.loads(flags_path.read_text())['arguments']
optimization = [arg for arg in arguments if arg.startswith('-O')]
assert optimization == ['-O2']
prior_source_parent = Path(build['masterOriginalPath']).parent
cache = Path(tempfile.mkdtemp(prefix='openshsm-master-compile-', dir='/private/tmp'))
obj = cache / 'fixed.cpp.o'
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-I', str(prior_source_parent), '-c', str(source), '-o', str(obj)]
compiled = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-2500:]
def text_bytes(path):
    dump = subprocess.check_output(['/usr/bin/otool', '-s', '__TEXT', '__text', str(path)], text=True)
    lines = dump.splitlines()
    assert lines[1] in ('Contents of (__TEXT,__text) section', '(__TEXT,__text) section')
    return '\n'.join(lines[2:]).encode()
before, after = text_bytes(original_obj), text_bytes(obj)
assert before == after, 'Reproduced O2 master text differs; do not infer current flags from recipe alone'
current_path = root / 'window-scheduler-o2/build.json'
current = json.loads(current_path.read_text())
assert str(original_obj) in current['linkCommand']
assert current['retainedInputs'][str(original_obj)] == sha(original_obj)
(output / 'verification.json').write_text(json.dumps({
    'result': 'CURRENT_MASTER_O2_FLAG_PRAGMA_OPTIMIZE_OFF_TEXT_REPRODUCED',
    'buildSha256': sha(build_path), 'builderSha256': sha(builder), 'currentBuildSha256': sha(current_path),
    'sourceSha256': sha(source), 'originalObjectSha256': sha(original_obj),
    'reproducedObjectPath': str(obj), 'reproducedObjectSha256': sha(obj),
    'textDumpSha256': hashlib.sha256(before).hexdigest(), 'flagsRecordSha256': sha(flags_path),
    'compileCommand': command, 'verifierSha256': sha(Path(__file__)),
    'limits': ['Actual executable __TEXT,__text disassembly bytes/address dump equal using inherited O2 recipe; debug sections/whole objects can differ.',
        'Flags includeO2 but master source explicitly disables clang optimization; effective O0 guard preserved, no performance fix.',
        'No master/runtime/source/IRQ behavior modification; pure helper draft stopped at contradictory flag assertion.',
        'Existing original-native endpoint tests remain limited; equality does not prove full original Wii longjmp/runtime correctness.']}, indent=2) + '\n')
print('CURRENT_MASTER_O2_FLAG_PRAGMA_OPTIMIZE_OFF_TEXT_REPRODUCED', hashlib.sha256(before).hexdigest())
