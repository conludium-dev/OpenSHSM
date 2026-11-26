"""Integrate latch/count/chunk pacing in existing DSP and expose existing AI DMA-rate state."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-adma-chunks'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-dsp-supply/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
old_archive = root / 'window-dsp-supply/libnwiiruntime.a'
assert sha(old_archive) == parent['archiveSha256']
records = json.loads((root / 'window-quantization/build.json').read_text())['compiled']
old_dsp = root / 'window-dsp-supply/hw_dsp.cpp'
assert sha(old_dsp) == parent['sourceSha256']
text = old_dsp.read_text()
patches = []
def replace(before, after):
    global text
    assert text.count(before) == 1, before
    text = text.replace(before, after)
    patches.append([before, after])

replace('static uint64_t s_adma_event_id = 0;', '''static uint64_t s_adma_event_id = 0;
static uint64_t s_adma_irq_id = 0;
static uint64_t s_adma_period = 0;
static openshsm::experiment::AdmaCursor adma_cursor;
static openshsm::experiment::AdmaTickPhase adma_phase;
static openshsm::experiment::AdmaOutput adma_output;
uint32_t ai_dma_sample_rate();''')
start = text.index('static void adma_event_cb(')
end = text.index('// three DSP subsystem', start)
before = text[start:end]
after = '''static void adma_event_cb(CPUContext& ctx, uint64_t late);

static void adma_schedule(CPUContext& ctx, uint64_t late) {
    s_adma_period = adma_phase.next(ctx.tb_freq, ai_dma_sample_rate());
    s_adma_event_id = EventScheduler::get().schedule_after(
        s_adma_period > late ? s_adma_period - late : 0, adma_event_cb);
}

static void adma_cancel() {
    EventScheduler::get().cancel(s_adma_event_id);
    EventScheduler::get().cancel(s_adma_irq_id);
    s_adma_event_id = s_adma_irq_id = 0;
}

static void adma_event_cb(CPUContext& ctx, uint64_t late) {
    if (!(adma_control & 0x8000)) {
        return;
    }
    if (!g_mmu) {
        throw std::runtime_error("ADMA memory is not initialized");
    }
    const auto chunk = adma_cursor.transfer(adma_addr, adma_control);
    const uint32_t va = chunk.address | 0x80000000;
    int16_t samples[16];
    for (unsigned i = 0; i < 16; ++i) {
        samples[i] = int16_t(g_mmu->read16(va + i * 2));
    }
    {
        std::lock_guard<std::mutex> lock(adma_mutex);
        const auto before = adma_ring.size() / 2;
        adma_output.append(samples, 8, ai_dma_sample_rate(), adma_ring);
        const auto after = adma_ring.size() / 2;
        openshsm::experiment::dsp_supply_observer.produced(after - before, before,
            after, late, s_adma_period, true);
    }
    if (chunk.interrupt) {
        dsp_control |= 0x0008;
        dsp_update_pi();
    }
    adma_schedule(ctx, late);
}

'''
replace(before, after)
before = '''                if (!(adma_control & 0x8000)) return 0;
                return 0;'''
replace(before, '                return adma_cursor.blocks_left_register();')
replace('adma_addr = (adma_addr & 0x0000FFFF) | ((val & 0xFFFF) << 16);',
    'adma_addr = (adma_addr & 0x0000FFFF) | ((val & 0x1FFF) << 16);')
replace('adma_addr = (adma_addr & 0xFFFF0000) | (val & 0xFFFF);',
    'adma_addr = (adma_addr & 0xFFFF0000) | (val & 0xFFE0);')
before = '''                    s_adma_event_id = EventScheduler::get().schedule_recurring(g_ctx_ptr->tb_freq / 200, adma_event_cb);'''
replace(before, '''                    if (!g_ctx_ptr) {
                        throw std::runtime_error("ADMA CPU is not initialized");
                    }
                    adma_cursor.latch(adma_addr, adma_control);
                    adma_phase = {};
                    adma_schedule(*g_ctx_ptr, 0);
                    s_adma_irq_id = EventScheduler::get().schedule_after(17, [](CPUContext&, uint64_t) {
                        if (adma_control & 0x8000) {
                            dsp_control |= 0x0008;
                            dsp_update_pi();
                        }
                    });''')
before = '''                        EventScheduler::get().cancel(s_adma_event_id);
                        s_adma_event_id = 0;'''
replace(before, '''                        adma_cancel();
                        std::lock_guard<std::mutex> lock(adma_mutex);
                        adma_output.finish(adma_ring);''')
replace('''                if ((val16 & 0x0001) || (was_halted && !is_halted)) {''',
    '''                if (val16 & 0x0001) {
                    adma_control = 0;
                    adma_cancel();
                    std::lock_guard<std::mutex> lock(adma_mutex);
                    adma_output.finish(adma_ring);
                }
                if ((val16 & 0x0001) || (was_halted && !is_halted)) {''')
text = '#include "stock_adma_cursor.h"\n#include "stock_adma_output.h"\n' + text
dsp_source = output / 'hw_dsp.cpp'
dsp_source.write_text(text)
ai_original = root / 'window-quantization/hw_ai.cpp'
ai_record = next(row for row in records if row['source'] == 'hw_ai.cpp')
assert sha(ai_original) == ai_record['sourceSha256']
ai_before = 'static uint32_t ai_cr = 0;'
ai_after = ai_before + '\nuint32_t ai_dma_sample_rate() { return (ai_cr & 0x40) ? 32000 : 48000; }'
assert ai_original.read_text().count(ai_before) == 1
ai_source = output / 'hw_ai.cpp'
ai_source.write_text(ai_original.read_text().replace(ai_before, ai_after))
compiled_rows = []
for name, source in [('hw_dsp.cpp', dsp_source), ('hw_ai.cpp', ai_source)]:
    record = next(row for row in records if row['source'] == name)
    obj = output / (name + '.o')
    compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
        '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
    (output / (name + '.log')).write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr[-3500:]
    compiled_rows.append({'source': str(source), 'sourceSha256': sha(source), 'object': str(obj), 'objectSha256': sha(obj)})
archive = output / 'libnwiiruntime.a'
archive.write_bytes(old_archive.read_bytes())
for row in compiled_rows:
    subprocess.run(['/usr/bin/ar', 'r', str(archive), row['object']], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
members = {}
for name, digest in parent['derivedArchiveMembers'].items():
    actual = hashlib.sha256(subprocess.run(['/usr/bin/ar', 'p', str(archive), name], check=True, capture_output=True).stdout).hexdigest()
    members[name] = actual
    if name not in ('hw_dsp.cpp.o', 'hw_ai.cpp.o'):
        assert actual == digest
command = list(parent['linkCommand'])
command[command.index(str(old_archive))] = str(archive)
exe = output / 'OpenSHSMStockADMAChunks'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
(output / 'build.json').write_text(json.dumps({'result': 'ADMA_CHUNKS_INTEGRATED_EXECUTION_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'compiled': compiled_rows, 'patches': patches,
    'aiPatch': [ai_before, ai_after], 'archiveSha256': sha(archive), 'members': members,
    'linkCommand': command, 'executableSha256': sha(exe), 'retainedLinkInputs': parent['retainedLinkInputs'],
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), public / 'stock_adma_cursor.h',
        public / 'stock_adma_output.h', public / 'stock_dsp_supply.h', ai_original]},
    'limits': ['Existing DSP cursor/ring and AI register rate; two runtime objects only, all75guests/main unchanged.',
        'SDL48→32 conversion is PC adaptation; start IRQ17TB ticks follows emulator200CPU-cycle heuristic, not hardware proof.',
        'No global clock/scheduler change; native component/live/audio verification required before use.']}, indent=2) + '\n')
print('ADMA_CHUNKS_INTEGRATED_EXECUTION_UNVERIFIED')
