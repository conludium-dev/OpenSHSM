"""Run existing actual texture/CPU/frame/timer gates on the ordered-execution candidate."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-pe-execute'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
gpu_path = output / 'gpu-pipeline-verification.json'
gpu = json.loads(gpu_path.read_text())
assert gpu['buildSha256'] == sha(build_path)
assert gpu['result'] == 'ACTUAL_FIFO_RENDER_REAL_GL_FENCE_BEFORE_PE_ACK_PASS6'
gl_base = Path('experiments/wii-static-recomp/verify_stock_texture_late_gl.py')
gl_script = gl_base.read_text().replace("output = root / 'window-texture-late'", "output = root / 'window-pe-execute'")
gl_script = gl_script.replace("parent_path = root / 'window-dispatch-select/build.json'", "parent_path = root / 'window-texture-late/build.json'")
gl_script = gl_script.replace("*build['arguments']", "*parent['arguments']")
exec(compile(gl_script, str(gl_base), 'exec'), {'__file__': __file__})
base = Path('experiments/wii-static-recomp/verify_stock_dispatch_select.py')
script = base.read_text()
start = script.index("before, after = build['abiRename']")
end = script.index("base = Path('experiments/wii-static-recomp/verify_stock_scheduler_o2.py')", start)
validation = Path('experiments/wii-static-recomp/verify_stock_pe_execute.py').read_text()
validation_start = validation.index('for path, digest in')
validation_end = validation.index('cache = Path(tempfile.mkdtemp', validation_start)
script = script[:start] + 'import subprocess\n' + validation[validation_start:validation_end] + script[end:]
script = script.replace('window-dispatch-select', 'window-pe-execute')
script = script.replace('window-vi-busy-latch/build.json', 'window-texture-late/build.json')
script = script.replace('DISPATCH_SELECT_DEC9_CALLBACK4_SDK7_SC3_LATE18', 'PE_EXECUTE_DEC9_CALLBACK4_SDK7_SC3_LATE18')
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
report.update(result='PE_EXECUTE_GL172_EVICTION1600_GPU6_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED',
    gpuProofSha256=sha(gpu_path), glProofSha256=sha(output / 'gl-verification.json'),
    glBaseVerifierSha256=sha(gl_base), cpuBaseVerifierSha256=sha(base))
report['limits'] = ['Only parser/GX-prefix/renderer completion behavior changes, all other linked inputs exact.',
    'Real GPU pipeline6/glFinish-before-ack, cache pixels172/eviction1600 in4settings and actualCPU/SDK/SC/18lateYUV-PPC/timer3 pass.',
    'No original textured scene/guest wait-loop/full asynchronous GPU hardware or live performance/coherence/visual/audio acceptance.',
    'Conservative glFinish can add waits, observed source cadence and coherence must be checked before promotion.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
