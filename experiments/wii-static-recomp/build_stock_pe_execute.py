"""Move PE acknowledgement into existing ordered GPU command execution."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-texture-late/build.json'
parent = json.loads(parent_path.read_text())
component_path = parent_path.parent / 'component-verification.json'
assert json.loads(component_path.read_text())['buildSha256'] == sha(parent_path)
assert json.loads(component_path.read_text())['result'] == 'TEXTURE_LATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL'
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
proof_path = root / 'pe-parse-ack-proof/verification.json'
assert json.loads(proof_path.read_text())['buildSha256'] == sha(parent_path)
archive_old = Path(parent['archivePath'])
assert sha(archive_old) == parent['archiveSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-pe-execute-', dir='/private/tmp'))
archive = cache / 'libnwiiruntime.a'
shutil.copyfile(archive_old, archive)
parser = root / 'headless-tev-banks/fifo_parser.cpp'
gx = root / 'headless-tev-banks/gx.cpp'
renderer = root / 'headless-texture-units/renderer_gl.cpp'
signal = '''        if (reg == 0x45 && (val & 0xFF) == 2) {
            nwii::runtime::hw::pe_signal_finish();
        } else if (reg == 0x47) {
            nwii::runtime::hw::pe_signal_token(val & 0xFFFF, false);
        } else if (reg == 0x48) {
            nwii::runtime::hw::pe_signal_token(val & 0xFFFF, true);
        }'''
parser_patches = [[signal, ''], ['    void ApplyBPRegisterImpl(uint8_t reg, uint32_t val) {',
    '    void ApplyBPRegisterImpl(uint8_t reg, uint32_t val) {\n' + signal]]
gx_text = gx.read_text()
start = gx_text.index('    int last_frame_end = -1;')
end = gx_text.index('    if (last_frame_end < 0)', start)
gx_patches = [[gx_text[start:end], '''    const auto execution = stock_gx_execution_bounds(s_carry);
    const int last_frame_end = execution.end;
    const int prev_frame_end = execution.previous_copy;
''']]
render_patches = [['        ApplyBPRegister((uint8_t)cmd.reg, cmd.val);', '''        if (stock_gx_pe_completion(cmd)) {
            glFinish();
        }
        ApplyBPRegister((uint8_t)cmd.reg, cmd.val);''']]
records = json.loads((root / 'headless-tev-banks/build.json').read_text())['compiled']
changes = {}
for original, patches, include in [(parser, parser_patches, ''), (gx, gx_patches, '#include "stock_gx_completion.h"\n'),
    (renderer, render_patches, '#include "stock_gx_completion.h"\n')]:
    original_obj = original.with_suffix('.cpp.o')
    current = subprocess.check_output(['/usr/bin/ar', '-p', str(archive_old), original_obj.name])
    assert hashlib.sha256(current).hexdigest() == sha(original_obj), original.name
    arguments = next(row['arguments'] for row in records if row['member'] == original_obj.name)
    expected_source = json.loads((root / 'headless-texture-units/build.json').read_text())['sourceSha256'] if original == renderer else next(
        row['sourceSha256'] for row in records if row['member'] == original_obj.name)
    assert sha(original) == expected_source
    text = original.read_text()
    for before, after in patches:
        assert text.count(before) == 1
        text = text.replace(before, after, 1)
    text = include + text
    restored = text.removeprefix(include) if include else text
    for before, after in reversed(patches):
        if after:
            assert restored.count(after) == 1
            restored = restored.replace(after, before, 1)
        else:
            offset = original.read_text().index(before)
            restored = restored[:offset] + before + restored[offset:]
    assert restored == original.read_text()
    source, obj = cache / original.name, cache / original_obj.name
    source.write_text(text)
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-I', str(original.parent),
        '-c', str(source), '-o', str(obj)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=120)
    assert compiled.returncode == 0, compiled.stderr[-3000:]
    subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
    changes[original.name] = {'originalPath': str(original), 'originalSha256': sha(original),
        'sourcePath': str(source), 'sourceSha256': sha(source), 'objectPath': str(obj), 'objectSha256': sha(obj),
        'patches': patches, 'include': include, 'compileCommand': command}
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
members = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', str(archive_old)], text=True).splitlines():
    if member.startswith('__'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(archive_old), member])
    after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    if member not in {Path(row['objectPath']).name for row in changes.values()}:
        assert before == after
    members[member] = hashlib.sha256(after).hexdigest()
link = list(parent['linkCommand'])
link[link.index(str(archive_old))] = str(archive)
exe = cache / 'OpenSHSMStockPEExecute'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
output = root / 'window-pe-execute'
output.mkdir(exist_ok=True)
retained = {}
for arg in link:
    if Path(arg).suffix in ('.o', '.a') and arg != str(archive):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        retained[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({'result': 'PE_ORDERED_EXECUTION_BUILT_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'changes': changes, 'members': members,
    'archivePath': str(archive), 'archiveSha256': sha(archive), 'linkCommand': link,
    'executablePath': str(exe), 'executableSha256': sha(exe),
    'retainedInputs': retained,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_gx_completion.h', proof_path]},
    'limits': ['PE signals at ApplyBPRegister during Render, conservative glFinish before acknowledgement.',
        'Existing carry consumes copy/finish/token completed prefixes, same copy-derived stale-draw filtering; no new queue.',
        'All three modified objects inherit current flags, no source/asset overwrite; native/GL/live verification pending.',
        'Headless without renderer does not execute/ack GPU commands; no claim full headless game support.']}, indent=2) + '\n')
print('PE_ORDERED_EXECUTION_BUILT_UNVERIFIED', exe)
