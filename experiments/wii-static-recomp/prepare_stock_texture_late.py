"""Prepare a delayed private copy of the existing bounded texture observer."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original = public / 'stock_texture_observation.h'
text = original.read_text()
patches = [
    ('#include <tuple>', '#include <tuple>\n#include <chrono>\n#include "stock_movie_capture_gate.h"\n#include "stock_texture_coherence.h"'),
    ('    static unsigned sequence = 0;', '''    static stock_movie_capture_gate::Gate gate(std::getenv("NWII_TEXTURE_CAPTURE_AFTER_MS"));
    if (!gate.valid) {
        return;
    }
    if (gate.delay_us != 0) {
        const auto now_us = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        if (!gate.accept(uint64_t(now_us))) {
            return;
        }
    }
    static unsigned sequence = 0;''')]
for before, after in patches:
    assert text.count(before) == 1
    text = text.replace(before, after, 1)
restored = text
for before, after in reversed(patches):
    restored = restored.replace(after, before, 1)
assert restored == original.read_text()
helpers = '''inline stock_movie_capture_gate::Gate& texture_observation_gate() {
    static stock_movie_capture_gate::Gate value(std::getenv("NWII_TEXTURE_CAPTURE_AFTER_MS"));
    return value;
}
inline uint64_t texture_observation_host_us() {
    return uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
inline TextureSourceSample begin_texture_source(nwii::runtime::CPUContext& ctx,
    const nwii::runtime::gx::TexStage& stage) {
    if (!std::getenv("NWII_TEXTURE_OBSERVE") || !std::getenv("NWII_TEXTURE_COHERENCE")) {
        return {};
    }
    static stock_movie_capture_gate::Gate gate(std::getenv("NWII_TEXTURE_CAPTURE_AFTER_MS"));
    const auto now = texture_observation_host_us();
    if (!gate.accept(now) || stage.width == 0 || stage.height == 0 ||
        stage.width > 1024 || stage.height > 1024) {
        return {};
    }
    static unsigned samples = 0;
    static uint64_t copied = 0;
    const auto size = nwii::runtime::hle::texture_data_size(stage.width, stage.height, stage.format);
    if (samples >= 128 || copied + size > 96 * 1024 * 1024) {
        return {};
    }
    auto sample = sample_texture_source(ctx, stage.base_addr, size, now);
    if (!sample.bytes.empty()) {
        ++samples;
        copied += sample.bytes.size();
    }
    return sample;
}
'''
marker = 'namespace openshsm::experiment {\n'
assert text.count(marker) == 1
text = text.replace(marker, marker + helpers, 1)
gate_declaration = 'static stock_movie_capture_gate::Gate gate(std::getenv("NWII_TEXTURE_CAPTURE_AFTER_MS"));'
assert text.count(gate_declaration) == 2
text = text.replace(gate_declaration, 'auto& gate = texture_observation_gate();')
coherence_patches = [
    ('uint32_t hash, const Image& image) {', 'uint32_t hash, const Image& image, const TextureSourceSample& before = {}) {'),
    ('bytes_written + size + rgba_size + palette >', 'bytes_written + size + rgba_size + palette + before.bytes.size() >'),
    ('    data.write(reinterpret_cast<const char*>(raw), size);', '''    TextureSourceSample after;
    if (!before.bytes.empty()) {
        after = sample_texture_source(ctx, stage.base_addr, size, texture_observation_host_us());
        if (after.bytes.empty()) {
            return;
        }
        std::ofstream earlier(prefix + ".before.raw", std::ios::binary);
        std::ofstream coherence(prefix + ".coherence.txt");
        if (!earlier || !coherence) {
            return;
        }
        earlier.write(reinterpret_cast<const char*>(before.bytes.data()), before.bytes.size());
        const auto difference = compare_texture_sources(before, after);
        coherence << before.host_us << ' ' << after.host_us << ' ' << before.hash << ' ' << after.hash
            << ' ' << difference.comparable << ' ' << difference.changed << ' '
            << difference.first << ' ' << difference.last << '\\n';
        if (!earlier || !coherence) {
            return;
        }
        bytes_written += before.bytes.size();
        raw = after.bytes.data();
    }
    data.write(reinterpret_cast<const char*>(raw), size);''')]
for before, after in coherence_patches:
    assert text.count(before) == 1
    text = text.replace(before, after, 1)
cache = Path(tempfile.mkdtemp(prefix='openshsm-texture-late-prepare-', dir='/private/tmp'))
header = cache / original.name
header.write_text(text)
gate_probe = public / 'stock_movie_capture_gate_probe.cpp'
exe = cache / 'capture-gate-probe'
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20', '-O2',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk', str(gate_probe), '-o', str(exe)]
compiled = subprocess.run(command, capture_output=True, text=True, timeout=30)
assert compiled.returncode == 0, compiled.stderr[-3000:]
run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
assert run.returncode == 0 and 'MOVIE_CAPTURE_DELAY_BOUNDARY_INVALID_CLOCK_PASS' in run.stdout
coherence_probe = public / 'stock_texture_coherence_probe.cpp'
coherence_exe = cache / 'coherence-probe'
coherence_command = command[:-3] + [str(coherence_probe), '-o', str(coherence_exe)]
compiled = subprocess.run(coherence_command, capture_output=True, text=True, timeout=30)
assert compiled.returncode == 0, compiled.stderr[-3000:]
coherence_run = subprocess.run([str(coherence_exe)], capture_output=True, text=True, timeout=10)
assert coherence_run.returncode == 0 and 'TEXTURE_SOURCE_RANGE_CONTIGUITY_COPY_READONLY_DIFFERENCE_PASS' in coherence_run.stdout
texture_path = root / 'window-texture-o2/build.json'
texture = json.loads(texture_path.read_text())
source = root / 'headless-texture-eviction/texture_cache_gl.cpp'
assert sha(source) == texture['sourceSha256']
prepared = cache / source.name
source_before = '    Image img = decode_texture(ctx, stage);\n    openshsm::experiment::observe_texture(ctx, stage, hash, img);'
source_after = '''    const auto source_before = openshsm::experiment::begin_texture_source(ctx, stage);
    Image img = decode_texture(ctx, stage);
    openshsm::experiment::observe_texture(ctx, stage, hash, img, source_before);'''
assert source.read_text().count(source_before) == 1
prepared.write_text(source.read_text().replace(source_before, source_after, 1))
assert prepared.read_text().replace(source_after, source_before, 1) == source.read_text()
obj = cache / 'texture_cache_gl.cpp.o'
runtime_command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *texture['arguments'],
    '-H', '-c', str(prepared), '-o', str(obj)]
compiled = subprocess.run(runtime_command, capture_output=True, text=True, timeout=90)
assert compiled.returncode == 0, compiled.stderr[-3000:]
assert str(header) in compiled.stderr
assert str(public / 'stock_movie_capture_gate.h') in compiled.stderr
assert str(public / 'stock_texture_coherence.h') in compiled.stderr
output = root / 'texture-late-preparation'
output.mkdir(exist_ok=True)
(output / 'verification.json').write_text(json.dumps({
    'result': 'EXISTING_TEXTURE_OBSERVER_DELAY_GATE_PREPARED_COMPILED',
    'originalHeaderSha256': sha(original), 'preparedHeaderPath': str(header), 'preparedHeaderSha256': sha(header),
    'patches': patches, 'coherencePatches': coherence_patches, 'helpers': helpers,
    'sourcePatch': [source_before, source_after], 'sourceSha256': sha(source), 'preparedSourcePath': str(prepared),
    'preparedSourceSha256': sha(prepared),
    'objectPath': str(obj), 'objectSha256': sha(obj), 'runtimeCompileCommand': runtime_command,
    'privateHeaderResolvedByCompiler': True,
    'gateProbeCommand': command, 'gateProbeStdout': run.stdout,
    'coherenceProbeCommand': coherence_command, 'coherenceProbeStdout': coherence_run.stdout,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), original,
        public / 'stock_movie_capture_gate.h', public / 'stock_texture_coherence.h', coherence_probe, gate_probe, source]},
    'limits': ['Private observer copy only; public original header/current runtime/executable unchanged.',
        'Existing shared gate class reused with texture-specific setting, no new timer/thread/cache/queue.',
        'Unset/zero bypass new clock read; invalid decimal/empty/negative/out-of-range fails closed, backward-clock tested.',
        'Existing128records/96MiB/perkey2/address/image/palette guards unchanged and evaluated after late gate.',
        'Delay starts at first eligible observer call after cache-miss decode, not process/movie start.',
        'Only actual texture object compiled; enabled observer bounds/pixel regression/link/live late capture pending.',
        'Optional NWII_TEXTURE_COHERENCE captures bounded before/after copies/full FNV hashes/byte differences; extra before file counted within96MiB.',
        'Copying shared guest RAM does not synchronize its producer or guarantee atomic/stable snapshot; no race/visual fix claim.',
        'One shared diagnostic gate origin (begin when coherence enabled, post otherwise), record both timestamps; not timing-neutral.',
        'Standalone range/copy test uses deterministic memory fixture, not full original runtime/producer thread synchronization proof.']}, indent=2) + '\n')
print('EXISTING_TEXTURE_OBSERVER_DELAY_GATE_PREPARED_COMPILED', obj)
