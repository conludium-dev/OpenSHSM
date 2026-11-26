"""Run exact presentation body with post-swap FIFO, including a copy arriving at swap."""
from pathlib import Path
import hashlib
import json

base = Path(__file__).resolve().parent / 'verify_stock_completed_frame_gpu.py'
script = base.read_text()
old = "assert build['result'] == 'COMPLETED_FRAME_BUILT_UNVERIFIED'"
assert script.count(old) == 1
script = script.replace(old, "assert build['result'] == 'POST_PRESENT_DRAIN_BUILT_UNVERIFIED'")
script = script.replace("present_cases = public / 'stock_completed_frame_present_cases.inc'",
    "present_cases = public / 'stock_completed_frame_present_cases.inc'\npost_cases = public / 'stock_post_present_gpu_cases.inc'")
script = script.replace('static unsigned present_swaps = 0;',
    '''static unsigned present_swaps = 0;
static bool require_pe_clear_at_swap = false;
static bool inject_copy_at_swap = false;
static void post_viewport_finish() {
    GLint viewport[4];
    glGetIntegerv(GL_VIEWPORT, viewport);
    assert(viewport[0] == 0 && viewport[1] == 0 && viewport[2] == 640 && viewport[3] == 480);
    actual_finish();
}''')
old = '    SDL_GL_SwapWindow(window);\n    ++present_swaps;'
assert script.count(old) == 1
script = script.replace(old, '''    if (require_pe_clear_at_swap) {
        assert(nwii::runtime::hw::g_pe_sr.load() == 0);
    }
    if (inject_copy_at_swap) {
        append(0x52, 0x4000);
        inject_copy_at_swap = false;
    }
''' + old)
old = "present_cases.read_text() + '\\n' + marker"
assert script.count(old) == 1
script = script.replace(old, "present_cases.read_text() + '\\n' + post_cases.read_text() + '\\n' + marker")
old = "prelude += present_block + '\\n}\\n#undef SDL_GL_SwapWindow\\n'"
assert script.count(old) == 1
script = script.replace(old, old + '''
primary_start = main_text.index('      host_phases.mark(1);')
primary_end = main_text.index('      host_phases.mark(2);', primary_start) + len('      host_phases.mark(2);')
primary_block = main_text[primary_start:primary_end]
prelude += "static void primary_from_current_main(bool headless) {\\nopenshsm::experiment::HostPhases host_phases;\\nconst bool trace_startup = false;\\nauto startup_trace = [](const char*) {};\\nhost_phases.begin(0);\\n" + primary_block + "\\n}\\n"
''')
scope = {'__file__': str(Path(__file__).resolve())}
exec(compile(script, str(base), 'exec'), scope)
path = scope['path']
report = json.loads(path.read_text())
assert 'POST_PRESENT_PE_ACK_AFTER_SWAP_TARGET_RESTORE_NEXT_COPY_PASS5' in report['stdout']
assert 'POST_PRESENT_NEXT_COPY_PRIMARY_READY_GATE_PASS' in report['stdout']
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
report.update(result='POST_PRESENT_ACTUAL_GPU_PE6_COPY4_PRESENT6_ORDER6_PASS',
    primaryBlockSha256=hashlib.sha256(scope['primary_block'].encode()).hexdigest(),
    baseVerifierSha256=sha(base), postCasesSha256=sha(scope['post_cases']))
report['limits'].append('Exact main block completes pending PE after swap before returning; new copy injected during swap remains ready for next presentation, not recursively swapped.')
report['limits'].append('Synthetic same-thread injection, not original asynchronous CPU/guest/VI/texture timing or full main-loop acceptance.')
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
