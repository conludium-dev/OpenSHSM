"""Reuse the actual post-present GPU suite with the BP-order archive and retained main."""
from pathlib import Path
import hashlib
import json

public = Path(__file__).resolve().parent
base = public / 'verify_stock_post_present_gpu.py'
code = base.read_text()
marker = "scope = {'__file__': str(Path(__file__).resolve())}"
assert code.count(marker) == 1
adaptation = '''
script = script.replace("assert build['result'] == 'POST_PRESENT_DRAIN_BUILT_UNVERIFIED'",
    "assert build['result'] == 'BP_PARSE_ORDER_BUILT_UNVERIFIED'")
setup = "build = json.loads(build_path.read_text())"
assert script.count(setup) == 1
script = script.replace(setup, setup + ''' + repr('''
parent_path = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline/window-post-present/build.json'
parent = json.loads(parent_path.read_text())
main_change = parent['changes']['main.cpp']
assert main_change['objectPath'] in build['linkCommand']
assert hashlib.sha256(Path(main_change['objectPath']).read_bytes()).hexdigest() == main_change['objectSha256']
assert hashlib.sha256(Path(build['sourcePath']).read_bytes()).hexdigest() == build['sourceSha256']
build['changes'] = {'main.cpp': main_change, 'fifo_parser.cpp': {
    'originalPath': build['originalSourcePath'], 'originalSha256': build['originalSourceSha256'],
    'sourcePath': build['sourcePath'], 'sourceSha256': build['sourceSha256'],
    'objectPath': build['objectPath'], 'objectSha256': build['objectSha256'], 'patches': build['patches']}}
''') + ''')
'''
code = code.replace(marker, adaptation + '\n' + marker)
compiler_marker = "scope = {'__file__': str(Path(__file__).resolve())}"
compiler_adaptation = '''
compiler = "command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(main_source.parent),"
assert script.count(compiler) == 1
script = script.replace(compiler, "command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(root / 'headless-tev-banks/include'), '-I', str(main_source.parent),")
'''
code = code.replace(compiler_marker, compiler_adaptation + '\n' + compiler_marker)
scope = {'__file__': str(Path(__file__).resolve())}
exec(compile(code, str(base), 'exec'), scope)
path = scope['path']
report = json.loads(path.read_text())
assert report['result'] == 'POST_PRESENT_ACTUAL_GPU_PE6_COPY4_PRESENT6_ORDER6_PASS'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
inner = scope['scope']
build = inner['build']
state_header = inner['root'] / 'headless-tev-banks/include/runtime/gx_state.h'
assert str(state_header) in inner['compile_log'].read_text()
assert hashlib.sha256(__import__('subprocess').check_output(['/usr/bin/ar', '-p', build['archivePath'],
    'fifo_parser.cpp.o'])).hexdigest() == build['objectSha256']
report.update(result='BP_ORDER_ACTUAL_FIFO_PE6_COPY4_PRESENT6_POST_ORDER6_PASS',
    wrapperSha256=sha(Path(__file__).resolve()), postVerifierSha256=sha(base),
    inheritedMainBuildSha256=sha(inner['parent_path']), stateHeaderPath=str(state_header), stateHeaderSha256=sha(state_header))
report['limits'].append('Candidate parser archive used; retained post-present main source/object verified, not a synthetic runtime replacement.')
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
