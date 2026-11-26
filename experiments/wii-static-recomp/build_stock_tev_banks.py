"""Build private latched TEV banks with a consistent GXState dependency closure."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from stock_tev_bank_patch import state, parser, renderer
from stock_tev_scope_patch import generator, renderer as scoped_renderer

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'headless-tev-banks'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base_path = root / 'headless-sc-pc/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['dependencies'].items():
    assert sha(Path(path)) == expected
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
old_archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
records = json.loads((root / 'window-quantization/build.json').read_text())['compiled']
by_member = {row['object']: row for row in records}
original_header = root / 'upstream-source/nWiiRuntime/include/runtime/gx_state.h'
header = output / 'include/runtime/gx_state.h'
header.parent.mkdir(parents=True, exist_ok=True)
header.write_text(state(original_header.read_text()))
compiler = '/Library/Developer/CommandLineTools/usr/bin/c++'
def run(cmd, log, cwd=None, timeout=180):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-4000:]
    return result.stdout

archive = output / 'libnwiiruntime.a'
shutil.copy2(old_archive, archive)
compiled = []
retained = {}
closure = []
members = subprocess.check_output(['/usr/bin/ar', '-t', str(old_archive)], text=True).splitlines()
for member in members:
    if member.startswith('__'):
        continue
    data = subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
    record = by_member[member]
    candidates = [path for path in root.glob('*/' + member)
        if path.with_suffix('').is_file() and hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(data).digest()]
    assert candidates, ('Cannot recover actual compiled source', member)
    original = candidates[0].with_suffix('')
    arguments = ['-I', str(output / 'include'), *record['arguments']]
    dependencies = run([compiler, *arguments, '-MM', str(original)], output / (member + '.deps.log'))
    if str(header) not in dependencies:
        retained[member] = hashlib.sha256(data).hexdigest()
        continue
    closure.append(member)
    text = original.read_text()
    if member == 'fifo_parser.cpp.o':
        text = parser(text)
    elif member == 'renderer_gl.cpp.o':
        text = renderer(scoped_renderer(text))
    elif member == 'tev_shader_gen.cpp.o':
        text = generator(text)
    source, obj = output / record['source'], output / member
    source.write_text(text)
    run([compiler, *arguments, '-c', str(source), '-o', str(obj)], output / (member + '.log'))
    subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
    compiled.append({'member': member, 'originalSource': str(original), 'originalSourceSha256': sha(original),
        'sourceSha256': sha(source), 'objectSha256': sha(obj), 'arguments': arguments})
    print('GXSTATE_REBUILT', member, flush=True)
assert {'gx.cpp.o', 'fifo_parser.cpp.o', 'renderer_gl.cpp.o', 'tev_shader_gen.cpp.o', 'texture_cache_gl.cpp.o'} <= set(closure)
for member, expected in retained.items():
    assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])).hexdigest() == expected
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
command[command.index(str(old_archive))] = str(archive)
main_record = by_member['main.cpp.o']
old_main = next(Path(arg) for arg in command if Path(arg).name == 'main.cpp.o')
assert sha(old_main) == main_record['objectSha256']
main_original = old_main.with_suffix('')
assert sha(main_original) == main_record['sourceSha256']
main_source, main_obj = output / 'main.cpp', output / 'main.cpp.o'
main_source.write_text(main_original.read_text())
main_args = ['-I', str(output / 'include'), *main_record['arguments']]
run([compiler, *main_args, '-c', str(main_source), '-o', str(main_obj)], output / 'main-compile.log')
command[command.index(str(old_main))] = str(main_obj)
exe = output / 'OpenSHSMStockTEVBanks'
command[command.index('-o') + 1] = str(exe)
run(command, output / 'link.log', root / 'export/build')
contract_obj = output / 'contract-entry.cpp.o'
run([compiler, *main_args, '-Dmain=stock_prototype_main', '-c', str(main_source), '-o', str(contract_obj)], output / 'contract-compile.log')
renderer_source = output / 'renderer_gl.cpp'
text = renderer_source.read_text()
start = text.index('  auto decode11 = ')
end = text.index('\n  static const bool s_tevtrace', start)
uniforms_source = output / 'uniforms.cpp'
uniforms_source.write_text('#include "runtime/gx_state.h"\nusing namespace nwii::runtime::gx;\n'
    'void stock_read_tev_uniforms(float* color, float* kcolor) {\n' + text[start:end] + '\n}\n')
probe_objs = []
for name, source in [('uniforms', uniforms_source), ('probe', public / 'stock_tev_bank_retention_probe.cpp')]:
    obj = output / (name + '.cpp.o')
    run([compiler, *main_args, '-c', str(source), '-o', str(obj)], output / (name + '-compile.log'))
    probe_objs.append(obj)
probe_cmd = list(command)
probe_cmd[probe_cmd.index(str(main_obj))] = str(contract_obj)
probe_cmd[1:1] = [str(obj) for obj in probe_objs]
probe = output / 'retention-probe'
probe_cmd[probe_cmd.index('-o') + 1] = str(probe)
run(probe_cmd, output / 'probe-link.log', root / 'export/build')
stdout = run([str(probe)], output / 'probe.log')
assert 'TEV_BANK_RETENTION_FIFO_REPLAY_PASS 8' in stdout
(output / 'build.json').write_text(json.dumps({'result': 'TEV_BANKS_BUILT_COMPONENT_PASS_GAME_UNVERIFIED',
    'baseBuildSha256': sha(base_path), 'originalGXHeaderSha256': sha(original_header), 'gxHeaderSha256': sha(header),
    'compiled': compiled, 'dependencyClosure': closure, 'retainedRuntimeMembers': retained,
    'archiveSha256': sha(archive), 'executableSha256': sha(exe), 'linkCommand': command,
    'mainSourceSha256': sha(main_source), 'mainObjectSha256': sha(main_obj),
    'probeSha256': sha(probe), 'probeLogSha256': sha(output / 'probe.log'),
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_tev_bank_patch.py',
        public / 'stock_tev_scope_patch.py', public / 'stock_tev_bank_retention_probe.cpp']},
    'retainedLinkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).suffix == '.o' and arg != str(main_obj)},
    'limits': ['All archived runtime GXState dependencies preprocessed and rebuilt; main rebuilt with same header.',
        'Independent bank retention at existing replay boundary; raw BP/decoder signed11 semantics preserved.',
        'SC correction/actual inherited sources retained; shader scoping/compile checks included.',
        'Synthetic FIFO/component only; actual GL uniform upload/pixels/live movie/Wii hardware remain unverified.']}, indent=2) + '\n')
print('TEV_BANKS_BUILT_COMPONENT_PASS_GAME_UNVERIFIED', len(closure))
