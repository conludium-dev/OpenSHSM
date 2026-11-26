"""Add one exact native SDK continuation; retain the existing dispatcher fallback and all other objects."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-movie-dma', root / 'window-sdk-enable-resume'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockMovieDMA') == build['executableSha256']
command = list(build['linkCommand'])
original = next(Path(arg) for arg in command if Path(arg).name == 'main_output.cpp.o').with_suffix('')
text = original.read_text()
assert '{0x8021750C, func_80217500}' not in text
matches = [(a, b, fn) for a, b, fn in re.findall(r'\{0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+), (func_[0-9A-Fa-f]+)\}', text)
    if int(a, 16) <= 0x8021750C < int(b, 16)]
assert matches[0][2] == 'func_801B55B0'
marker = '    {0x80217500, func_80217500},'
assert text.count(marker) == 1
fixed = text.replace(marker, marker + '\n    {0x8021750C, func_80217500},')
extension = """
extern "C" int sdk_enable_route(uint32_t target) {
    if (auto function = lookup_dispatch(target)) {
        return function == func_80217500 ? 2 : -1;
    }
    for (const auto& bound : g_func_bounds) {
        if (target >= bound.start && target < bound.end) {
            return bound.func == func_80217500 ? 1 : 0;
        }
    }
    return -2;
}
extern "C" void sdk_enable_dispatch(CPUContext& ctx) {
    if (auto function = lookup_dispatch(ctx.pc)) {
        function(ctx);
        return;
    }
    for (const auto& bound : g_func_bounds) {
        if (ctx.pc >= bound.start && ctx.pc < bound.end) {
            bound.func(ctx);
            return;
        }
    }
    nwii::runtime::interpret_step(ctx);
}
"""
full = json.loads((root / 'window-quantization/build.json').read_text())
arguments = next(row['arguments'] for row in full['compiled'] if row['source'] == 'main_output.cpp')
probe_source = Path('experiments/wii-static-recomp/stock_sdk_enable_resume_probe.cpp').resolve()
probe_obj = output / 'probe.cpp.o'
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(probe_source), '-o', str(probe_obj)],
    check=True, capture_output=True, timeout=60)
records = {}
for variant, body in [('baseline', text), ('fixed', fixed)]:
    source, obj = output / (variant + '.cpp'), output / (variant + '.cpp.o')
    source.write_text(body + extension)
    subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments, '-c', str(source), '-o', str(obj)],
        check=True, capture_output=True, timeout=60)
    probe_command = list(command)
    probe_command[probe_command.index(str(original) + '.o')] = str(obj)
    probe_command[probe_command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
    probe_command.insert(1, str(probe_obj))
    exe = output / (variant + '-probe')
    probe_command[probe_command.index('-o') + 1] = str(exe)
    subprocess.run(probe_command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    result = subprocess.run([str(exe), *(['baseline'] if variant == 'baseline' else [])], capture_output=True, text=True, timeout=20)
    (output / (variant + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith('ROUTE ' + ('0' if variant == 'baseline' else '2') + '\n')
    records[variant] = {'sourceSha256': sha(source), 'objectSha256': sha(obj), 'executableSha256': sha(exe),
        'logSha256': sha(output / (variant + '.log')), 'linkCommand': probe_command}
command[command.index(str(original) + '.o')] = str(output / 'fixed.cpp.o')
exe = output / 'OpenSHSMStockSDKEnableResume'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
(output / 'build.json').write_text(json.dumps({'result': 'EXACT_SDK_ENABLE_RESUME_COMPONENT_PASS',
    'baseBuildSha256': sha(base / 'build.json'), 'originalPath': str(original), 'originalSha256': sha(original),
    'baselineFirstRange': matches[0], 'resumeAddress': '8021750C', 'expectedFunction': '80217500',
    'records': records, 'probeSourceSha256': sha(probe_source), 'probeObjectSha256': sha(probe_obj),
    'linkCommand': command, 'executableSha256': sha(exe),
    'retainedInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file()
        and Path(arg).suffix in ('.o', '.a') and arg != str(output / 'fixed.cpp.o')},
    'limits': ['Baseline query proves foreign fallback selection, not incorrect interpreted output or the live movie stop cause.',
        'Fixed exact native resume7logical mask/PC/GPR fixtures; no whole callback/IRQ/hardware oracle.',
        'No forced EE/guard/counter/clock/queue state; original SDK native continuation only.']}, indent=2) + '\n')
print('Exact SDK resume route/component PASS; baseline foreign range,7native resume fixtures')
