"""Execute newly analyzed/generated cache code through the existing callback runtime."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
emitter = root / 'sc-emitter-research'
output = emitter / 'native-execution'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
emitter_manifest = emitter / 'comparison.json'
generation = json.loads(emitter_manifest.read_text())
for path, expected in generation['dependencies'].items():
    assert sha(Path(path)) == expected
record = next(row for row in generation['functions'] if row['function'] == '0x80212fd0')
base_path = root / 'headless-cache-irq-observe/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
retained = root / 'headless-cache-irq-observe/output_38.cpp'
assert sha(retained) == base['sourceSha256']
prefix = retained.read_text().split('void func_', 1)[0]
prefix += '\nextern bool probe_arm_sc;\nextern "C" void probe_cache_flush(CPUContext&);\n'
arguments = json.loads((root / 'window-fp-guard/output_38.cpp.record.json').read_text())['arguments']
compiler = '/Library/Developer/CommandLineTools/usr/bin/c++'
def run(command, log, cwd=None):
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd, timeout=120)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    return result.stdout

probe_source = public / 'stock_sc_resume_probe.cpp'
probe_obj = output / 'probe.cpp.o'
run([compiler, *arguments, '-c', str(probe_source), '-o', str(probe_obj)], output / 'probe-compile.log')
command = list(base['linkCommand'])
command[command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
results = {}
for name in ('baseline', 'corrected'):
    generated = emitter / name / (str(0x80212FD0) + '.cpp')
    assert sha(generated) == record[name + 'Sha256']
    text = generated.read_text().replace('void func_80212FD0(', 'void probe_cache_flush(')
    marker = 'loc_80212FF8: ;\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '''    if (probe_arm_sc) {
        probe_arm_sc = false;
        ctx.msr = 0x8000;
        ctx.queue_callback(0x80004000, 0, 0);
    }
''')
    source, obj = output / (name + '.cpp'), output / (name + '.cpp.o')
    source.write_text(prefix + text)
    run([compiler, *arguments, '-c', str(source), '-o', str(obj)], output / (name + '-compile.log'))
    cmd = list(command)
    cmd[1:1] = [str(obj), str(probe_obj)]
    exe = output / (name + '-probe')
    cmd[cmd.index('-o') + 1] = str(exe)
    run(cmd, output / (name + '-link.log'), root / 'export/build')
    stdout = run([str(exe), *(['baseline'] if name == 'baseline' else [])], output / (name + '.log'))
    expected = 'STALE_SC_PC_RESUME_REPRODUCED' if name == 'baseline' else 'SYNCHRONIZED_SC_PC_RETURN_PASS'
    assert expected in stdout
    results[name] = {'result': expected, 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'executableSha256': sha(exe), 'logSha256': sha(output / (name + '.log'))}
(output / 'comparison.json').write_text(json.dumps({'result': 'DOL_ANALYZER_COMPILED_EMITTER_NATIVE_SC_RESUME_PASS',
    'emitterManifestSha256': sha(emitter_manifest), 'baseBuildSha256': sha(base_path), 'records': results,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), probe_source]},
    'limits': ['Fresh actual analyzer/emitter cache output; only fixture symbol rename and controlled callback availability added.',
        'Three alignment cases, existing callback/save/load/return; simulated callback completion, no callback body execution.',
        'Not full runtime integration, live movie performance, Wii hardware SC handler or visual acceptance.']}, indent=2) + '\n')
print('DOL_ANALYZER_COMPILED_EMITTER_NATIVE_SC_RESUME_PASS')
