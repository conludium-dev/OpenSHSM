"""Serialize completed IPC replies in an isolated full-runtime build."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import argparse
from stock_audio_patch import adapt_audio
from stock_cp_patch import adapt_cp

parser = argparse.ArgumentParser()
parser.add_argument('--audio', action='store_true')
parser.add_argument('--natural-alarms', action='store_true')
parser.add_argument('--gl-diagnostics', action='store_true')
parser.add_argument('--projection-guard', action='store_true')
parser.add_argument('--cp-breakpoint', action='store_true')
args = parser.parse_args()
assert not args.natural_alarms or args.audio
assert not args.gl_diagnostics or args.natural_alarms
assert not args.projection_guard or args.gl_diagnostics
assert not args.cp_breakpoint or args.projection_guard

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
build = root / 'export/build'
variant = 'ipc-cpbp' if args.cp_breakpoint else 'ipc-glguard' if args.projection_guard else 'ipc-gldiag' if args.gl_diagnostics else 'ipc-natural' if args.natural_alarms else 'ipc-audio' if args.audio else 'ipc-queue'
output = root / variant
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original = root / 'export/nWiiRuntime/src/hw/hw_ipc.cpp'
text = original.read_text()
replacements = [
    ('#include <algorithm>', '#include <algorithm>\n#include <deque>'),
    ('uint32_t ipc_ppc_msg = 0;', '''uint32_t ipc_ppc_msg = 0;
static std::deque<uint32_t> completed_replies;

static void publish_reply() {
    if ((ipc_ppc_ctrl & 0x04) || completed_replies.empty()) {
        return;
    }
    ipc_arm_msg = completed_replies.front();
    completed_replies.pop_front();
    ipc_arm_ctrl |= 0x02;
    ipc_ppc_ctrl |= 0x04;
    g_ipc_interrupt_delay = 50;
}

static void complete_reply(uint32_t address) {
    completed_replies.push_back(address & 0x1FFFFFFF);
    publish_reply();
}'''),
    ('  ipc_arm_msg  = virt_addr & 0x1FFFFFFF;\n  ipc_arm_ctrl = 0x00000003;', '''    if (result != -0x70000001) {
        complete_reply(virt_addr);
    }
    ipc_arm_ctrl |= 0x01;'''),
    ('''  ipc_arm_msg = req_addr & 0x1FFFFFFF;
  ipc_arm_ctrl = 0x00000002;
  ipc_ppc_ctrl |= 0x00000004;
  g_ipc_interrupt_delay = 5000;''', '    complete_reply(req_addr);'),
    ('''  ipc_arm_msg = req_addr & 0x1FFFFFFF;
  ipc_ppc_ctrl &= ~0x01;
  ipc_ppc_ctrl |= 0x26; 
  g_ipc_interrupt_delay = 50;''', '    complete_reply(req_addr);'),
    ('ipc_ppc_ctrl |= 0x26;', 'ipc_ppc_ctrl |= 0x02;'),
    ('ipc_ppc_ctrl |= 0x2C;', 'ipc_ppc_ctrl |= 0x02;'),
    ('                (void)old_ctrl;', '                publish_reply();\n                (void)old_ctrl;'),
]
for old, new in replacements:
    assert text.count(old) == 1, old
    text = text.replace(old, new)
source = output / 'hw_ipc.cpp'
source.write_text(text)
flags = (build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
obj = output / 'hw_ipc.cpp.o'
result = subprocess.run([compiler, *arguments, '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
objects = [obj]
audio_original = root / 'export/nWiiRuntime/src/hw/hw_ai.cpp'
if args.audio:
    audio_source = output / 'hw_ai.cpp'
    audio_source.write_text(adapt_audio(audio_original.read_text()))
    audio_obj = output / 'hw_ai.cpp.o'
    result = subprocess.run([compiler, *arguments, '-c', str(audio_source), '-o', str(audio_obj)], capture_output=True, text=True, timeout=120)
    (output / 'audio-compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    objects.append(audio_obj)
ios_original = root / 'export/nWiiRuntime/src/hle/ios.cpp'
if args.natural_alarms:
    ios_text = ios_original.read_text()
    marker = '      {\n          static uint32_t dec_same_pc_count = 0;'
    end_marker = '      static uint32_t dcount = 0;'
    assert ios_text.count(marker) == 1 and ios_text.count(end_marker) == 1
    start = ios_text.index(marker)
    end = ios_text.index(end_marker, start)
    removed = ios_text[start:end]
    assert removed.count('ctx.mmu.write32(') == 2
    assert 'force-expired alarm' in removed
    ios_source = output / 'ios.cpp'
    ios_source.write_text(ios_text[:start] + ios_text[end:])
    ios_obj = output / 'ios.cpp.o'
    result = subprocess.run([compiler, *arguments, '-c', str(ios_source), '-o', str(ios_obj)], capture_output=True, text=True, timeout=120)
    (output / 'ios-compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    objects.append(ios_obj)
renderer_original = root / 'export/nWiiRuntime/src/hle/gx/renderer_gl.cpp'
if args.gl_diagnostics:
    renderer_text = renderer_original.read_text()
    renderer_changes = [
        ('static void FlushBatch() {', '''static void DiagnoseGL(const char* phase) {
    if (!gx_trace()) {
        return;
    }
    GLenum error = glGetError();
    if (error != GL_NO_ERROR) {
        printf("[GLPHASE] %s error=0x%x\\n", phase, error);
    }
}

static void FlushBatch() {'''),
        ('  if (!s_vao) {', '  DiagnoseGL("before batch setup");\n  if (!s_vao) {'),
        ('  glDrawArrays(GL_TRIANGLES, 0, s_batch.size());', '  DiagnoseGL("before draw");\n  glDrawArrays(GL_TRIANGLES, 0, s_batch.size());'),
        ('  glUseProgram(s_active_shader.id);', '  DiagnoseGL("before program bind");\n  glUseProgram(s_active_shader.id);'),
        ('  ApplyProjection(s_active_shader.uProjMtx);\n  ApplyZMode();', '  ApplyProjection(s_active_shader.uProjMtx);\n  DiagnoseGL("projection upload");\n  ApplyZMode();'),
    ]
    if args.projection_guard:
        renderer_changes.append(('  if (uProj < 0)\n    return;', '    if (uProj < 0 || s_active_shader.id == 0) {\n        return;\n    }'))
    for old, new in renderer_changes:
        assert renderer_text.count(old) == 1, old
        renderer_text = renderer_text.replace(old, new)
    renderer_source = output / 'renderer_gl.cpp'
    renderer_source.write_text(renderer_text)
    renderer_obj = output / 'renderer_gl.cpp.o'
    result = subprocess.run([compiler, *arguments, '-c', str(renderer_source), '-o', str(renderer_obj)], capture_output=True, text=True, timeout=120)
    (output / 'renderer-compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    objects.append(renderer_obj)
cp_original = root / 'export/nWiiRuntime/src/hw/hw_cp.cpp'
if args.cp_breakpoint:
    cp_source = output / 'hw_cp.cpp'
    cp_source.write_text(adapt_cp(cp_original.read_text()))
    cp_obj = output / 'hw_cp.cpp.o'
    result = subprocess.run([compiler, *arguments, '-c', str(cp_source), '-o', str(cp_obj)], capture_output=True, text=True, timeout=120)
    (output / 'cp-compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    objects.append(cp_obj)
base_archive = build / 'nWiiRuntime/libnwiiruntime.a'
archive = output / 'libnwiiruntime.a'
base_hash = sha(base_archive)
members = subprocess.check_output(['/usr/bin/ar', '-t', str(base_archive)], text=True).splitlines()
assert members.count(obj.name) == 1
shutil.copy2(base_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), *map(str, objects)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
unchanged = {}
for member in members:
    if member in {item.name for item in objects} or member.startswith('__.SYMDEF'):
        continue
    old = subprocess.check_output(['/usr/bin/ar', '-p', str(base_archive), member])
    new = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert old == new, member
    unchanged[member] = hashlib.sha256(old).hexdigest()
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
exe = output / {'ipc-cpbp': 'OpenSHSMStockIPCCPBP', 'ipc-glguard': 'OpenSHSMStockIPCGLGuard', 'ipc-gldiag': 'OpenSHSMStockIPCGLDiag',
    'ipc-natural': 'OpenSHSMStockIPCNatural', 'ipc-audio': 'OpenSHSMStockIPCAudio',
    'ipc-queue': 'OpenSHSMStockIPCQueue'}[variant]
command[command.index('-o') + 1] = str(exe)
assert command.count('nWiiRuntime/libnwiiruntime.a') == 1
command[command.index('nWiiRuntime/libnwiiruntime.a')] = str(archive)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
assert sha(base_archive) == base_hash
(output / 'build.json').write_text(json.dumps({
    'result': 'IPC_COMPLETION_QUEUE_BUILT_EXECUTION_PENDING',
    'builderSha256': sha(Path(__file__)), 'baseSourceSha256': sha(original),
    'sourceSha256': sha(source), 'baseArchiveSha256': base_hash,
    'audioEnabled': args.audio,
    'naturalAlarms': args.natural_alarms,
    'cpBreakpoint': args.cp_breakpoint,
    'cpSourceSha256': sha(cp_source) if args.cp_breakpoint else None,
    'cpBaseSha256': sha(cp_original),
    'glDiagnostics': args.gl_diagnostics, 'projectionGuard': args.projection_guard,
    'rendererSourceSha256': sha(renderer_source) if args.gl_diagnostics else None,
    'rendererBaseSha256': sha(renderer_original),
    'iosSourceSha256': sha(ios_source) if args.natural_alarms else None,
    'iosBaseSha256': sha(ios_original),
    'audioPatchSha256': sha(project / 'experiments/wii-static-recomp/stock_audio_patch.py'),
    'audioSourceSha256': sha(audio_source) if args.audio else None,
    'audioBaseSha256': sha(audio_original),
    'archiveSha256': sha(archive), 'executableSha256': sha(exe),
    'unchangedRuntimeMembers': unchanged,
    'retainedObjects': {item: sha(build / item) for item in command if item.endswith('.cpp.o')},
    'limits': ['Host IPC adaptation: FIFO of actual completed requests, pending requests excluded.',
        'Guest enable bits retained; ACK and reply flags separated; existing interrupt delay retained.',
        'Not physical Wii timing, full IOS fidelity or graphical acceptance.']
}, indent=2) + '\n')
print('Built IPC queue variant;', len(unchanged), 'other runtime objects retained')
