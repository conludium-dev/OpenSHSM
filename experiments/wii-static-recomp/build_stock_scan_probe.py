"""Link a scan probe to the exact restored runtime and current generated modules."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--continuation-routes', action='store_true')
parser.add_argument('--scan-observe', action='store_true')
parser.add_argument('--consumption', action='store_true')
parser.add_argument('--numeric-reader', action='store_true')
parser.add_argument('--flight', action='store_true')
args = parser.parse_args()
assert not args.scan_observe or args.continuation_routes
assert not args.consumption or (args.scan_observe and args.continuation_routes)
assert not args.numeric_reader or args.consumption
assert not args.flight or args.numeric_reader
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
full = root / 'window-quantization'
output = root / ('window-numeric-flight' if args.flight else 'window-numeric-reader' if args.numeric_reader else 'window-scan-consume' if args.consumption else 'window-scan-observe' if args.scan_observe else 'window-scan-routes' if args.continuation_routes else 'window-scan-restore')
build = json.loads((output / 'build.json').read_text())
parent = json.loads((full / 'build.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
item = next(row for row in parent['compiled'] if row['source'] == 'gx.cpp')
source = Path('experiments/wii-static-recomp/stock_scan_probe.cpp').resolve()
obj, exe = output / 'scan-probe.cpp.o', output / 'scan-probe'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *item['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command = list(build['linkCommand'])
dispatcher = output / 'probe-dispatcher.cpp'
contract = """
    static bool routes_checked = false;
    if (!routes_checked) {
        for (uint32_t address = 0x8019D438; address < 0x8019D564; address += 4) {
            if (lookup_dispatch(address) != func_8019D434) {
                throw std::runtime_error("original scan continuation route mismatch");
            }
        }
        if (lookup_dispatch(0x8019D434) != dispatch_hle_8019D434) {
            throw std::runtime_error("original scan entry route mismatch");
        }
        routes_checked = true;
        std::cout << "SCAN_ROUTES 76\\n";
    }
""" if args.continuation_routes else ''
original_dispatcher = Path(build.get('dispatcherPath', str(next(Path(arg) for arg in command if Path(arg).name == 'main_output.cpp.o').with_suffix(''))))
dispatcher.write_text(original_dispatcher.read_text() + """
extern "C" void scan_probe_dispatch(CPUContext& ctx) {
""" + contract + """
    const uint32_t target = ctx.pc;
    if (auto function = lookup_dispatch(target)) {
        function(ctx);
        return;
    }
    for (const auto& bound : g_func_bounds) {
        if (bound.start == 0) { break; }
        if (target >= bound.start && target < bound.end) {
            bound.func(ctx);
            return;
        }
    }
    nwii::runtime::interpret_step(ctx);
}
""")
dispatch_obj = output / 'probe-dispatcher.cpp.o'
arguments = next(row for row in parent['compiled'] if row['source'] == 'main_output.cpp')['arguments']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(dispatcher), '-o', str(dispatch_obj)], capture_output=True, text=True, timeout=60)
(output / 'probe-dispatch-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
command[command.index(str(original_dispatcher.with_name('main_output.cpp.o')))] = str(dispatch_obj)
command[command.index(str(full / 'main.cpp.o'))] = str(full / 'contract-entry.cpp.o')
command.insert(1, str(obj))
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=60)
(output / 'probe-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
(output / 'probe-build.json').write_text(json.dumps({'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executableSha256': sha(exe), 'parentBuildSha256': sha(output / 'build.json'), 'command': command,
    'continuationRoutes': args.continuation_routes,
    'scanObserve': args.scan_observe,
    'consumption': args.consumption,
    'dispatcherSourceSha256': sha(dispatcher), 'dispatcherObjectSha256': sha(dispatch_obj),
    'linkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a')}}, indent=2) + '\n')
print('Built exact restored scanner probe')
