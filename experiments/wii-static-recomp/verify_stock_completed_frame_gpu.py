"""Validate actual carry/renderer readiness and PE; not main-loop presentation."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
args = parser.parse_args()
build_path = args.build.resolve()
build = json.loads(build_path.read_text())
root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert build['result'] == 'COMPLETED_FRAME_BUILT_UNVERIFIED'
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(path) == digest
for row in build['changes'].values():
    assert sha(row['originalPath']) == row['originalSha256']
    text = Path(row['originalPath']).read_text()
    for before, after in row['patches']:
        assert text.count(before) == 1
        text = text.replace(before, after, 1)
    assert text == Path(row['sourcePath']).read_text()
    assert sha(row['sourcePath']) == row['sourceSha256']
    assert sha(row['objectPath']) == row['objectSha256']
assert sha(build['archivePath']) == build['archiveSha256']
assert sha(build['executablePath']) == build['executableSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-completed-frame-gpu-', dir='/private/tmp'))
base = public / 'stock_pe_gpu_pipeline_probe.cpp'
cases = public / 'stock_completed_frame_gpu_cases.inc'
present_cases = public / 'stock_completed_frame_present_cases.inc'
main_source = Path(build['changes']['main.cpp']['sourcePath'])
main_text = main_source.read_text()
start = main_text.index('      host_phases.mark(3);')
end = main_text.index('      if (trace_startup) { startup_trace("audio begin"); }', start)
present_block = main_text[start:end]
prelude = '''
#include <array>
#include "stock_debug_overlay.h"
#include "stock_host_phases.h"
static unsigned present_swaps = 0;
static std::array<unsigned char, 3> expected_present{};
static void checked_present_swap(SDL_Window* window) {
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
    glReadBuffer(GL_BACK);
    unsigned char pixel[4];
    glReadPixels(16, 16, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    for (unsigned channel = 0; channel < 3; ++channel) {
        assert(std::abs(int(pixel[channel]) - int(expected_present[channel])) <= 1);
    }
    SDL_GL_SwapWindow(window);
    ++present_swaps;
}
#define SDL_GL_SwapWindow checked_present_swap
static void present_from_current_main(SDL_Window* window, GLuint efb_fbo, bool headless) {
    openshsm::experiment::HostPhases host_phases;
    openshsm::experiment::DebugOverlay debug_overlay;
    const bool trace_startup = false;
    auto startup_trace = [](const char*) {};
    host_phases.begin(0);
'''
prelude += present_block + '\n}\n#undef SDL_GL_SwapWindow\n'
text = base.read_text()
marker = '    glad_glFinish = actual_finish;'
assert text.count(marker) == 1
assert text.count('int main() {') == 1
text = text.replace('int main() {', prelude + '\nint main() {', 1)
text = '#include "runtime/gx_state.h"\n' + text.replace(marker,
    cases.read_text() + '\n' + present_cases.read_text() + '\n' + marker, 1)
source = cache / 'probe.cpp'
source.write_text(text)
obj = cache / 'probe.cpp.o'
flags_path = root / 'window-movie-late/build.json'
flags = json.loads(flags_path.read_text())['changes']['37']['arguments']
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(main_source.parent),
    *flags, '-UNDEBUG', '-H',
    '-c', str(source), '-o', str(obj)]
run = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert run.returncode == 0, run.stderr[-3000:]
compile_log = cache / 'compile.log'
compile_log.write_text(run.stdout + run.stderr)
assert str(main_source.parent / 'stock_debug_overlay.h') in run.stderr
assert str(public / 'stock_host_phases.h') in run.stderr
link = list(build['linkCommand'])
main = build['changes']['main.cpp']['objectPath']
entry = root / 'headless-tev-banks/contract-entry.cpp.o'
link[link.index(main)] = str(entry)
link.insert(1, str(obj))
exe = cache / 'completed-frame-gpu-probe'
link[link.index('-o') + 1] = str(exe)
run = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert run.returncode == 0, run.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=60)
assert run.returncode == 0, run.stdout + run.stderr
assert 'ACTUAL_FIFO_RENDER_REAL_GL_FENCE_BEFORE_PE_ACK_PASS6' in run.stdout
assert 'COMPLETED_COPY_READY_STATS_DEFERRED_PE_REAL_GL_PASS4' in run.stdout
assert 'EXACT_MAIN_PRESENT_BLOCK_REAL_BLIT_SWAP_GATE_PASS6' in run.stdout
report = {'result': 'COMPLETED_FRAME_ACTUAL_GPU_PE6_COPY4_PRESENT6_PASS', 'buildSha256': sha(build_path),
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), base, cases, present_cases,
        main_source, main_source.parent / 'stock_debug_overlay.h', public / 'stock_host_phases.h', flags_path, entry]},
    'presentationBlockSha256': hashlib.sha256(present_block.encode()).hexdigest(),
    'compileLogPath': str(compile_log), 'compileLogSha256': sha(compile_log),
    'sourcePath': str(source), 'sourceSha256': sha(source), 'compileCommand': command,
    'linkCommand': link, 'executablePath': str(exe), 'executableSha256': sha(exe),
    'stdout': run.stdout, 'stderr': run.stderr,
    'limits': ['Actual FIFO/drain/renderer with real GL fences, six existing PE cases and four new copy/readiness/statistics cases.',
        'Copy followed by completion is acknowledged on the next drain, not lost.',
        'Exact generated-main presentation block extracted unchanged; real blit/backbuffer RGB and forwarded SDL swap checked in six cases.',
        'Main object replaced by probe entry; whole main loop, OS front-buffer pixels and enabled overlay not exercised.',
        'No original textured scene, live guest wait-loop, cadence, audio or physical Wii acceptance.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(run.stdout)
