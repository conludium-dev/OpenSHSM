"""Private parser-only candidate: separate parsed BP values from executed GX state."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

project = Path(__file__).resolve().parents[2]
root = project / 'work/private-game/static-recomp/stock-baseline'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent_path = root / 'window-context-stage/build.json'
parent = json.loads(parent_path.read_text())
component_path = parent_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(parent_path)
assert component['result'] == 'CONTEXT_STAGE_CACHE234_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'
assert sha(parent['archivePath']) == parent['archiveSha256']
assert all(sha(path) == value for path, value in parent['retainedInputs'].items())
parser_build_path = root / 'window-pe-execute/build.json'
record = json.loads(parser_build_path.read_text())['changes']['fifo_parser.cpp']
original = Path(record['sourcePath'])
assert sha(original) == record['sourceSha256']
assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], 'fifo_parser.cpp.o'])).hexdigest() == record['objectSha256']
text = original.read_text()
start = text.index('    void ParseBP(uint8_t reg, uint32_t val) {')
end = text.index('    void ApplyBPRegisterImpl(uint8_t reg, uint32_t val) {', start)
patches = [[text[start:end], '''    void ParseBP(uint8_t reg, uint32_t val) {
        g_parse_bp[reg] = val;
    }

'''], ['static float g_parse_nrmmtx[96] = {0};',
    'static float g_parse_nrmmtx[96] = {0};\nstatic uint32_t g_parse_bp[256] = {0};'],
    ['void FifoParser::Parse(std::vector<uint8_t>& fifo, std::vector<GXCommand>& commands) {',
    '''void FifoParser::Parse(std::vector<uint8_t>& fifo, std::vector<GXCommand>& commands) {
    static const bool bp_initialized = [] {
        std::memcpy(g_parse_bp, g_state.bp, sizeof(g_parse_bp));
        return true;
    }();
    (void)bp_initialized;'''],
    ['uint32_t merged = (g_state.bp[reg] & ~mask) | (val & mask);',
     'uint32_t merged = (g_parse_bp[reg] & ~mask) | (val & mask);'],
    ['    h ^= g_state.xf[0x00E]; h *= 1099511628211ull;',
    '''    for (uint32_t value : g_parse_bp) {
        h ^= value;
        h *= 1099511628211ull;
    }
    h ^= g_state.xf[0x00E]; h *= 1099511628211ull;''']]
for before, after in patches:
    assert text.count(before) == 1
    text = text.replace(before, after, 1)
restored = text
for before, after in reversed(patches):
    assert restored.count(after) == 1
    restored = restored.replace(after, before, 1)
assert restored == original.read_text()
cache = Path(tempfile.mkdtemp(prefix='openshsm-bp-parse-order-', dir='/private/tmp'))
source, obj = cache / 'fifo_parser.cpp', cache / 'fifo_parser.cpp.o'
source.write_text(text)
command = list(record['compileCommand'])
command[command.index(str(original))] = str(source)
command[command.index('-o') + 1] = str(obj)
compiled = subprocess.run(command, capture_output=True, text=True, timeout=120)
(cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
archive = cache / 'libnwiiruntime.a'
shutil.copyfile(parent['archivePath'], archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
members = {}
for member in subprocess.check_output(['/usr/bin/ar', '-t', parent['archivePath']], text=True).splitlines():
    if member.startswith('__'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], member])
    after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert member == 'fifo_parser.cpp.o' or before == after
    members[member] = hashlib.sha256(after).hexdigest()
assert members['fifo_parser.cpp.o'] == sha(obj)
link = list(parent['linkCommand'])
link[link.index(parent['archivePath'])] = str(archive)
exe = cache / 'OpenSHSMStockBPParseOrder'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
report = {'result': 'BP_PARSE_ORDER_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'originalSourcePath': str(original), 'originalSourceSha256': sha(original), 'patches': patches,
    'sourcePath': str(source), 'sourceSha256': sha(source), 'objectPath': str(obj), 'objectSha256': sha(obj),
    'compileCommand': command, 'archivePath': str(archive), 'archiveSha256': sha(archive), 'members': members,
    'linkCommand': link, 'executablePath': str(exe), 'executableSha256': sha(exe),
    'retainedInputs': parent['retainedInputs'],
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), parent_path, component_path, parser_build_path]},
    'limits': ['Only parser object replaced; executed BP state changes only at existing ApplyBPRegister.',
        'Parser-local BP shadow supports ordered native RMW markers; display-list cache key includes this input state.',
        'Existing NOSEED switch no longer changes parse BP policy; no environment switch required for ordering.',
        'All other archive members/main/guest/CPU/audio/PE/presentation retained; unregistered, not default.',
        'Native correctness, GPU/menu/texture acceptance and performance pending; not original Wii reconstruction proof.']}
path = cache / 'build.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
