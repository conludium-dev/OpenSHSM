"""Reuse actual CPU/frame/timer regressions after checking the texture-only archive delta."""
from pathlib import Path
import hashlib
import json

base = Path('experiments/wii-static-recomp/verify_stock_dispatch_select.py')
script = base.read_text()
start = script.index("before, after = build['abiRename']")
end = script.index("base = Path('experiments/wii-static-recomp/verify_stock_scheduler_o2.py')", start)
script = script[:start] + '''before, after = build['sourcePatch']
assert Path(build['sourcePath']).read_text().replace(after, before, 1) == Path(build['originalSourcePath']).read_text()
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
assert sha(Path(build['archivePath'])) == build['archiveSha256']
assert sha(Path(build['textureObjectPath'])) == build['textureObjectSha256']
old_archive = parent['archivePath']
expected = list(parent['linkCommand'])
expected[expected.index(old_archive)] = build['archivePath']
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
import subprocess
for member, digest in build['members'].items():
    data = subprocess.check_output(['/usr/bin/ar', '-p', build['archivePath'], member])
    assert hashlib.sha256(data).hexdigest() == digest
    if member != 'texture_cache_gl.cpp.o':
        assert data == subprocess.check_output(['/usr/bin/ar', '-p', old_archive, member])
''' + script[end:]
script = script.replace('window-dispatch-select', 'window-texture-late')
script = script.replace('window-vi-busy-latch/build.json', 'window-dispatch-select/build.json')
script = script.replace('DISPATCH_SELECT_DEC9_CALLBACK4_SDK7_SC3_LATE18', 'TEXTURE_LATE_DEC9_CALLBACK4_SDK7_SC3_LATE18')
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/stock-baseline/window-texture-late')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
gl_path = output / 'gl-verification.json'
gl = json.loads(gl_path.read_text())
assert gl['result'] == 'LATE_TEXTURE_DISABLED_ENABLED_INVALID_GL_PIXELS172_EVICTION1600_EQUAL'
assert gl['buildSha256'] == report['buildSha256']
report.update(glProofSha256=sha(gl_path), wrapperVerifierSha256=sha(base))
report['limits'] = ['Only diagnostic texture member replaced, source hooks restored/allother archive and link inputs exact.',
    'Actual callback4/DEC9/SDK7/SC3/scheduler/18late YUV-PPC/timer3 and disabled/enabled/invalid realGL172pixels/1600evictions pass.',
    'Coherence copies unsynchronized; fixture equality not original producer stability/hardware/live visual acceptance or promotion.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
