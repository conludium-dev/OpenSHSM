"""Reuse current texture, CPU, original-packet and VI gates on the candidate."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--gpu-proof', type=Path, required=True)
args = parser.parse_args()
build_path = args.build.resolve()
output = build_path.parent
build = json.loads(build_path.read_text())
gpu_path = args.gpu_proof.resolve()
gpu = json.loads(gpu_path.read_text())
root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert gpu['result'] == 'COMPLETED_FRAME_ACTUAL_GPU_PE6_COPY4_PRESENT6_PASS'
assert gpu['buildSha256'] == sha(build_path)
for path, digest in {**build['dependencies'], **build['retainedInputs'], **gpu['dependencies']}.items():
    assert sha(path) == digest
assert sha(gpu['executablePath']) == gpu['executableSha256']
parent_path = root / 'window-pe-execute/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
for row in build['changes'].values():
    assert sha(row['originalPath']) == row['originalSha256']
    text = Path(row['originalPath']).read_text()
    for before, after in row['patches']:
        assert text.count(before) == 1
        text = text.replace(before, after, 1)
    assert text == Path(row['sourcePath']).read_text()
    assert sha(row['objectPath']) == row['objectSha256']
assert sha(build['archivePath']) == build['archiveSha256']
for member, digest in build['members'].items():
    current = subprocess.check_output(['/usr/bin/ar', '-p', build['archivePath'], member])
    assert hashlib.sha256(current).hexdigest() == digest
    if member != 'gx.cpp.o':
        assert current == subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], member])
expected = list(parent['linkCommand'])
expected[expected.index(parent['archivePath'])] = build['archivePath']
expected[expected.index(str(root / 'window-vi-timer/main.cpp.o'))] = build['changes']['main.cpp']['objectPath']
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
assert sha(build['executablePath']) == build['executableSha256']

def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)

gl_base = public / 'verify_stock_texture_late_gl.py'
script = replace_once(gl_base.read_text(), "output = root / 'window-texture-late'", f'output = Path({str(output)!r})')
script = replace_once(script, "parent_path = root / 'window-dispatch-select/build.json'",
    "parent_path = root / 'window-pe-execute/build.json'")
script = replace_once(script, "*build['arguments']",
    "*json.loads((root / 'window-texture-late/build.json').read_text())['arguments']")
exec(compile(script, str(gl_base), 'exec'), {'__file__': str(Path(__file__).resolve())})

cpu_base = public / 'verify_stock_scheduler_o2.py'
script = cpu_base.read_text()
start = script.index('assert sha(parent_path)')
end = script.index('temporary = Path(tempfile.mkdtemp', start)
script = script[:start] + script[end:]
script = replace_once(script, "output = root / 'window-scheduler-o2'", f'output = Path({str(output)!r})')
script = replace_once(script, "parent_path = root / 'window-movie-late/build.json'",
    "parent_path = root / 'window-pe-execute/build.json'")
script = replace_once(script, "flags = parent['changes']['37']['arguments']",
    "flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']['37']['arguments']")
script = replace_once(script,
    "('callback', public / 'stock_callback_runtime_probe.cpp', 'ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4'),",
    "('callback', public / 'stock_callback_runtime_probe.cpp', 'ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4'),\n"
    "    ('dec', public / 'stock_dec_ee_gate_probe.cpp', 'DEC_EE_MASK_DUE_HANDLER_NONLOCAL_ENDPOINT_PASS9'),")
assert script.count("name == 'callback'") == 2
script = script.replace("name == 'callback'", "name in ('callback', 'dec')")
script = replace_once(script, "assert prior['buildSha256'] == sha(parent_path)",
    "assert prior['buildSha256'] == sha(root / 'window-movie-late/build.json')")
start = script.index("command = list(prior['linkCommand'])")
end = script.index("exe = temporary / 'frame'", start)
script = script[:start] + """command = list(build['linkCommand'])
fixture = Path(prior['linkCommand'][1])
assert sha(fixture) == prior['objectSha256']
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(fixture))
""" + script[end:]
exec(compile(script, str(cpu_base), 'exec'), {'__file__': str(Path(__file__).resolve())})

timer_base = public / 'verify_stock_vi_timer_latch.py'
script = replace_once(timer_base.read_text(), "output = root / 'window-vi-busy-latch'", f'output = Path({str(output)!r})')
exec(compile(script, str(timer_base), 'exec'), {'__file__': str(Path(__file__).resolve())})
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
report.update(result='COMPLETED_FRAME_GL172_EVICTION1600_GPU16_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED',
    gpuProofPath=str(gpu_path), gpuProofSha256=sha(gpu_path),
    glProofSha256=sha(output / 'gl-verification.json'), timerProofSha256=sha(output / 'timer-latch-verification.json'),
    reusedVerifierSha256={str(path): sha(path) for path in [gl_base, cpu_base, timer_base]})
report['limits'] = ['Exact source/object/archive/link delta checked; only existing GX member and main replaced.',
    'Actual GL textures172/eviction1600 in four settings, PE6/copy4/exact presentation6, CPU/SDK/SC/late18/timer3 verified.',
    'Original packet YUV and selected PPC endpoints equal in isolated replay, not full live Wii behavior.',
    'Whole-game cadence/title/audio/coherence/controller acceptance and promotion still pending.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], report_path)
