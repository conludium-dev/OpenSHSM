"""Main-only experiment: execute the existing FIFO after swapping a completed frame."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent_path = root / 'window-pe-cadence/build.json'
parent = json.loads(parent_path.read_text())
proof_path = parent_path.parent / 'component-verification.json'
proof = json.loads(proof_path.read_text())
assert proof['buildSha256'] == sha(parent_path)
assert proof['result'] == 'PE_CADENCE_GPU16_SETTINGS3_RETAINED_PARENT_COMPONENTS_VERIFIED'
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(path) == digest
assert sha(parent['archivePath']) == parent['archiveSha256']
presentation_path = root / 'window-completed-frame/build.json'
presentation = json.loads(presentation_path.read_text())
record = presentation['changes']['main.cpp']
original = Path(record['sourcePath'])
assert sha(original) == record['sourceSha256']
assert sha(record['objectPath']) == record['objectSha256']
assert record['objectPath'] in parent['linkCommand']
before = '        if (trace_startup) { startup_trace("swap end"); }'
after = '''        if (trace_startup) { startup_trace("swap end"); }
        glBindFramebuffer(GL_FRAMEBUFFER, efb_fbo);
        glViewport(0, 0, 640, 480);
        ProcessGXFifo();
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        host_phases.mark(2);'''
text = original.read_text()
primary_before = '      if (trace_startup) { startup_trace("fifo begin"); }\n      ProcessGXFifo();'
primary_after = '''      if (trace_startup) { startup_trace("fifo begin"); }
      if (headless || !nwii::runtime::gx::g_state.frame_ready) {
          ProcessGXFifo();
      }'''
patches = [[before, after], [primary_before, primary_after]]
for old, new in patches:
    assert text.count(old) == 1
    text = text.replace(old, new, 1)
restored = text
for old, new in reversed(patches):
    assert restored.count(new) == 1
    restored = restored.replace(new, old, 1)
assert restored == original.read_text()
cache = Path(tempfile.mkdtemp(prefix='openshsm-post-present-', dir='/private/tmp'))
source, obj = cache / 'main.cpp', cache / 'main.cpp.o'
source.write_text(text)
overlay = original.parent / 'stock_debug_overlay.h'
assert sha(overlay) == presentation['dependencies'][str(root / 'window-vi-timer/stock_debug_overlay.h')]
shutil.copyfile(overlay, cache / overlay.name)
command = list(record['compileCommand'])
command[command.index(str(original))] = str(source)
command[command.index('-o') + 1] = str(obj)
command.insert(1, '-H')
run = subprocess.run(command, capture_output=True, text=True, timeout=180)
(cache / 'compile.log').write_text(run.stdout + run.stderr)
assert run.returncode == 0, run.stderr[-3000:]
assert str(cache / 'stock_debug_overlay.h') in run.stderr
assert str(public / 'stock_host_phases.h') in run.stderr
link = list(parent['linkCommand'])
link[link.index(record['objectPath'])] = str(obj)
exe = cache / 'OpenSHSMStockPostPresentDrain'
link[link.index('-o') + 1] = str(exe)
run = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert run.returncode == 0, run.stderr[-3000:]
retained = {path: digest for path, digest in parent['retainedInputs'].items() if path != record['objectPath']}
retained[parent['archivePath']] = parent['archiveSha256']
change = {'originalPath': str(original), 'originalSha256': sha(original), 'sourcePath': str(source),
    'sourceSha256': sha(source), 'objectPath': str(obj), 'objectSha256': sha(obj),
    'patches': patches, 'compileCommand': command}
report = {'result': 'POST_PRESENT_DRAIN_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'archivePath': parent['archivePath'], 'archiveSha256': parent['archiveSha256'], 'members': parent['members'],
    'changes': {'main.cpp': change}, 'linkCommand': link, 'executablePath': str(exe), 'executableSha256': sha(exe),
    'retainedInputs': retained, 'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(),
        proof_path, presentation_path, cache / 'stock_debug_overlay.h', public / 'stock_host_phases.h']},
    'limits': ['Only main object replaced; existing FIFO/drain/renderer/carry/CPU/VI/audio/timebase/sleep unchanged.',
        'Extra FIFO drain occurs after actual ready-frame swap; EFB bound for rendering then default framebuffer restored.',
        'Existing HostPhases mark(2) adds extra drain duration to GX without charging audio or swap.',
        'Another copy arriving during post-present drain stays frame_ready for the next loop; no recursive presentation.',
        'Primary drain skips while a frame from the previous post-present drain is ready, preventing partial tail from overwriting it before swap.',
        'PC scheduling adaptation; actual GPU and live cadence/coherence/visual/audio acceptance pending, not default.']}
path = cache / 'build.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
