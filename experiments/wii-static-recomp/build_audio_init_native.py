"""Execute the original compiled OS audio startup using the existing DSP backend."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-flush-syscall-boot'
output = private / 'audio-init-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original = Path('work/private-game/disc/DATA/sys/main.dol')
assert hashlib.sha1(original.read_bytes()).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
subprocess.run(['python3', str(experiment / 'verify_audio_trace_dolphin.py')], check=True)
build = json.loads((base / 'boot.json').read_text())
input_headers = {str(path): sha(path) for path in experiment.glob('*.h')}
for name in ('mass_boot.cpp', 'loader-bat-seed.h'):
    (output / name).write_bytes((base / name).read_bytes())
records = []
changes = []
reads = {0x80212d4c, 0x80212d58, 0x80212da0, 0x80212da8, 0x80212df0, 0x80212df8,
    0x80212e0c, 0x80212e18, 0x80212e28, 0x80212e58, 0x80212e68, 0x80212e78,
    0x80212d70, 0x80212e34, 0x80212e40, 0x80212d74, 0x80212e54}
writes = {0x80212d40, 0x80212d48, 0x80212d54, 0x80212d6c, 0x80212d8c, 0x80212d98,
    0x80212d9c, 0x80212db8, 0x80212ddc, 0x80212de8, 0x80212dec, 0x80212e08,
    0x80212e14, 0x80212e30, 0x80212e60, 0x80212e64, 0x80212e70}
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = {key: row[key] for key in ('file', 'source', 'sourceSha256', 'object', 'objectSha256')}
    if row['file'] == 'output_63.cpp':
        lines = Path(row['source']).read_text().splitlines(keepends=True)
        site = 0
        for index, line in enumerate(lines):
            match = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', line)
            if match:
                site = int(match[1], 16)
            before = line
            if site in reads and 'bat_memory_read16(ctx,' in line:
                line = line.replace('bat_memory_read16', 'experiment_audio_read16').replace('); //', f', 0x{site:08x}); //')
            elif site in writes and ('bat_memory_write16(ctx,' in line or 'experiment_si_query_write32(ctx,' in line):
                if 'bat_memory_write16' in line:
                    line = line.replace('bat_memory_write16', 'experiment_audio_write16').replace('); //', f', 0x{site:08x}); //')
                else:
                    line = line.replace('experiment_si_query_write32', 'experiment_audio_write32')
            if line != before:
                changes.append({'site': site, 'before': before, 'after': line})
                lines[index] = line
        assert {change['site'] for change in changes} == reads | writes
        source = output / row['file']
        source.write_text(''.join(lines))
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'dsp_startup_frontend.h'), '-I', str(runtime / 'include'),
            '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / 'compile.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        record.update(source=str(source), sourceSha256=sha(source), object=str(obj), objectSha256=sha(obj))
    records.append(record)
host = output / 'audio-host.cpp'
body = (experiment / 'exi_getid_host.cpp').read_text()
body = body[:body.index('int main(int argc, char** argv)')]
body = body.replace('    if (context.inst_count > 100000)',
    '    if (context.pc == 0x807f0000) { throw std::runtime_error("Audio oracle return sentinel"); }\n    if (context.inst_count > 1000000)')
body = body.replace('GetID instruction budget exceeded', 'Audio instruction budget exceeded')
host.write_text('#include "dsp_startup_frontend.h"\n#include "sram_frontend.h"\n' + body + (experiment / 'audio_init_host.cpp').read_text())
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    experiment / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
    runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'audio-init-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-include', str(experiment / 'dsp_startup_frontend.h'), '-DSHSM_SI_EXTERNAL_DELIVERY',
    '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-I', str(output), '-I', str(experiment),
    '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[r['object'] for r in records], '-o', str(exe)],
    capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
results = {}
for mode in ('normal', 'lost-dma', 'lost-mail', 'wrong-mail'):
    result = subprocess.run([str(exe), str(original), mode], capture_output=True, text=True, timeout=30)
    (output / (mode + '.log')).write_text(result.stdout + result.stderr)
    results[mode] = {'returnCode': result.returncode, 'logSha256': sha(output / (mode + '.log'))}
    print(mode, result.returncode, (result.stdout + result.stderr)[-300:])
(output / 'build.json').write_text(json.dumps({'result': 'AUDIO_NATIVE_REQUIRES_COMPARISON', 'records': records,
    'changes': changes, 'results': results, 'builderSha256': sha(Path(__file__)), 'baseSha256': sha(base / 'boot.json'),
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'headerHashes': input_headers, 'vendorDspSha256': sha(runtime / 'src/hw/hw_dsp.cpp'),
    'originalSha256': sha(original)}, indent=2) + '\n')
assert results['normal']['returnCode'] == 0
