"""Retain ADMA logical deadlines through an additive scheduler API, preserving existing methods/heap policy."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-adma-deadline'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-adma-accounting/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
original = root / 'window-adma-accounting/hw_dsp.cpp'
assert sha(original) == parent['sourceSha256']
patches = [
    ('static uint64_t s_adma_period = 0;', 'static uint64_t s_adma_period = 0;\nstatic uint64_t s_adma_next_due = 0;'),
    ('''static void adma_schedule(CPUContext& ctx, uint64_t late) {
    s_adma_period = adma_phase.next(ctx.tb_freq, ai_dma_sample_rate());
    s_adma_event_id = EventScheduler::get().schedule_after(
        s_adma_period > late ? s_adma_period - late : 0, adma_event_cb);
}''', '''static void adma_schedule(CPUContext& ctx) {
    s_adma_period = adma_phase.next(ctx.tb_freq, ai_dma_sample_rate());
    if (s_adma_next_due > UINT64_MAX - s_adma_period) {
        throw std::runtime_error("ADMA deadline overflow");
    }
    s_adma_next_due += s_adma_period;
    s_adma_event_id = EventScheduler::get().schedule_at(s_adma_next_due, adma_event_cb);
}'''),
    ('    s_adma_event_id = s_adma_irq_id = 0;', '    s_adma_event_id = s_adma_irq_id = s_adma_next_due = 0;'),
    ('    adma_schedule(ctx, late);', '    adma_schedule(ctx);'),
    ('                    adma_schedule(*g_ctx_ptr, 0);',
        '                    s_adma_next_due = EventScheduler::get().now();\n                    adma_schedule(*g_ctx_ptr);')]
text = original.read_text()
for before, after in patches:
    assert text.count(before) == 1, before
    text = text.replace(before, after)
source, obj = output / 'hw_dsp.cpp', output / 'hw_dsp.cpp.o'
source.write_text(text)
header = output / 'stock_adma_output.h'
header.write_bytes((root / 'window-adma-accounting/stock_adma_output.h').read_bytes())
record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'hw_dsp.cpp')
include = output / 'include/runtime'
include.mkdir(parents=True, exist_ok=True)
scheduler_header_original = root / 'export/nWiiRuntime/include/runtime/event_scheduler.h'
scheduler_header = include / 'event_scheduler.h'
header_marker = '    EventId schedule_after(uint64_t delay, Callback cb);'
header_addition = header_marker + '\n\n    // Preserve chronological ordering of overdue device events.\n    EventId schedule_at(uint64_t due, Callback cb);'
assert scheduler_header_original.read_text().count(header_marker) == 1
scheduler_header.write_text(scheduler_header_original.read_text().replace(header_marker, header_addition))
scheduler_original = root / 'window-quantization/event_scheduler.cpp'
scheduler_record = next(row for row in json.loads((root / 'window-quantization/build.json').read_text())['compiled'] if row['source'] == 'event_scheduler.cpp')
assert sha(scheduler_original) == scheduler_record['sourceSha256']
assert parent['members']['event_scheduler.cpp.o'] == scheduler_record['objectSha256']
scheduler_source, scheduler_obj = output / 'event_scheduler.cpp', output / 'event_scheduler.cpp.o'
source_marker = 'EventScheduler::EventId EventScheduler::schedule_after('
addition = '''EventScheduler::EventId EventScheduler::schedule_at(uint64_t due, Callback cb) {
    EventId id = m_next_id++;
    push({due, id, 0, std::move(cb)});
    return id;
}

'''
assert scheduler_original.read_text().count(source_marker) == 1
scheduler_source.write_text(scheduler_original.read_text().replace(source_marker, addition + source_marker))
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(output / 'include'), *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(output / 'include'), *scheduler_record['arguments'],
    '-c', str(scheduler_source), '-o', str(scheduler_obj)], capture_output=True, text=True, timeout=180)
(output / 'scheduler-compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
archive = output / 'libnwiiruntime.a'
old_archive = root / 'window-adma-accounting/libnwiiruntime.a'
assert sha(old_archive) == parent['archiveSha256']
archive.write_bytes(old_archive.read_bytes())
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ar', 'r', str(archive), str(scheduler_obj)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
members = {}
for name, digest in parent['members'].items():
    actual = hashlib.sha256(subprocess.run(['/usr/bin/ar', 'p', str(archive), name], check=True, capture_output=True).stdout).hexdigest()
    members[name] = actual
    if name not in ('hw_dsp.cpp.o', 'event_scheduler.cpp.o'):
        assert actual == digest
command = list(parent['linkCommand'])
command[command.index(str(old_archive))] = str(archive)
exe = output / 'OpenSHSMStockADMADeadline'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'ADMA_DEADLINE_BUILT_EXECUTION_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'sourceSha256': sha(source), 'objectSha256': sha(obj), 'patches': patches,
    'schedulerSourceSha256': sha(scheduler_source), 'schedulerObjectSha256': sha(scheduler_obj),
    'schedulerAddition': addition, 'schedulerHeaderPatch': [header_marker, header_addition],
    'executableSha256': sha(exe), 'archiveSha256': sha(archive), 'members': members, 'linkCommand': command,
    'retainedLinkInputs': parent['retainedLinkInputs'],
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), header, public / 'stock_adma_accounting.h',
        public / 'stock_adma_cursor.h', scheduler_header, scheduler_header_original, scheduler_original]},
    'limits': ['DSP deadline field/additive absolute scheduler API, existing scheduler methods/heap/layout unchanged.',
        'Two objects only; main/75guests/PCM/converter/IRQ policy retained, no parallel queue.',
        'Overdue ADMA callbacks keep logical phase until caught up; no old-frame interpolation or buffer enlargement.',
        'CPU handler interleaving/real hardware/lateness under host I/O still need separate validation.']}, indent=2) + '\n')
print('ADMA_DEADLINE_BUILT_EXECUTION_UNVERIFIED')
