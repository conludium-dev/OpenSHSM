"""Reproduce callback arrival exactly at original cache SC; correct PC, never clamp CTR."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'sc-resume-research'
output.mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
base_path = root / 'headless-cache-irq-observe/build.json'
base = json.loads(base_path.read_text())
for path, expected in base['retainedLinkInputs'].items():
    assert sha(Path(path)) == expected
original = root / 'headless-cache-irq-observe/output_38.cpp'
assert sha(original) == base['sourceSha256']
text = original.read_text()
start = text.index('void func_80212FD0(')
end = text.index('\nvoid func_', start + 1)
prefix = text[:text.index('void func_')]
body = text[start:end].replace('void func_80212FD0(', 'void probe_cache_flush(')
marker = 'loc_80212FF8: ;\n'
assert body.count(marker) == 1
body = body.replace(marker, marker + '''    if (probe_arm_sc) {
        probe_arm_sc = false;
        ctx.msr = 0x8000;
        ctx.queue_callback(0x80004000, 0, 0);
    }
''')
prefix += '\nextern bool probe_arm_sc;\nextern "C" void probe_cache_flush(CPUContext&);\n'
arguments = json.loads((root / 'window-fp-guard/output_38.cpp.record.json').read_text())['arguments']
def compile_file(source, obj):
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=60)
    (output / (obj.name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
probe_source, probe_obj = public / 'stock_sc_resume_probe.cpp', output / 'probe.cpp.o'
compile_file(probe_source, probe_obj)
command = list(base['linkCommand'])
command[command.index(str(root / 'window-quantization/main.cpp.o'))] = str(root / 'window-quantization/contract-entry.cpp.o')
results = {}
for name, fixed, flags in [('baseline', False, ['baseline']), ('corrected', True, [])]:
    current = body
    if fixed:
        marker = '    nwii::runtime::handle_syscall(ctx);'
        assert current.count(marker) == 1
        current = current.replace(marker, '    ctx.pc = 0x80212FF8;\n' + marker)
    source, obj = output / (name + '.cpp'), output / (name + '.cpp.o')
    source.write_text(prefix + current)
    compile_file(source, obj)
    cmd = list(command)
    cmd[1:1] = [str(obj), str(probe_obj)]
    exe = output / (name + '-probe')
    cmd[cmd.index('-o') + 1] = str(exe)
    subprocess.run(cmd, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
    result = subprocess.run([str(exe), *flags], capture_output=True, text=True, timeout=20)
    log = output / (name + '.log')
    log.write_text(result.stdout + result.stderr)
    expected = 'SYNCHRONIZED_SC_PC_RETURN_PASS' if fixed else 'STALE_SC_PC_RESUME_REPRODUCED'
    assert result.returncode == 0 and expected in result.stdout, (name, result.returncode, result.stdout[-4000:], result.stderr)
    results[name] = {'result': expected, 'sourceSha256': sha(source), 'objectSha256': sha(obj),
        'executableSha256': sha(exe), 'logSha256': sha(log)}
(output / 'comparison.json').write_text(json.dumps({'result': 'SC_BOUNDARY_CALLBACK_RESUME_DEFECT_REPRODUCED_AND_CORRECTED',
    'baseBuildSha256': sha(base_path), 'originalSourceSha256': sha(original), 'records': results,
    'probeSourceSha256': sha(probe_source), 'verifierSha256': sha(Path(__file__)),
    'limits': ['Actual retained cache body and existing callback/save/load, controlled availability exactly at SC boundary.',
        'Baseline returns to BDNZ with CTR0; corrected resumes SC and reaches original native return.',
        'Not live IRQ transition/hardware SC semantics or video performance proof; no guest callback body executed.']}, indent=2) + '\n')
print('SC_BOUNDARY_CALLBACK_RESUME_DEFECT_REPRODUCED_AND_CORRECTED')
