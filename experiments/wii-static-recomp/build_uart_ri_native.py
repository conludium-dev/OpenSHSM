"""Rebuild EXI batches with opt-in RI UART, preserving existing base objects."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-memory-protection-boot'
output = private / 'uart-ri-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_uart_ri_dolphin.py')], check=True)
build = json.loads((base / 'boot.json').read_text())
for name in ('mass_boot.cpp', 'loader-bat-seed.h', 'memory-protection-bat-plan.h'):
    (output / name).write_bytes((base / name).read_bytes())
records = []
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = {key: row[key] for key in ('file', 'source', 'sourceSha256', 'object', 'objectSha256')}
    if row['file'] in ('output_62.cpp', 'output_63.cpp'):
        source = output / row['file']
        source.write_bytes(Path(row['source']).read_bytes())
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'memory_protection_frontend.h'), '-I', str(output), '-I', str(runtime / 'include'),
            '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / (row['file'] + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-2500:]
        record.update(source=str(source), sourceSha256=sha(source), object=str(obj), objectSha256=sha(obj))
    records.append(record)
body = (experiment / 'exi_getid_host.cpp').read_text()
body = body[:body.index('int main(int argc, char** argv)')]
host_body = (experiment / 'uart_host.cpp').read_text().replace('0x2030', '0x2032')
host_body = host_body.replace('    g_trace_calls = false;', '    experimentExiRiUart = true;\n    g_trace_calls = false;')
host_body = host_body.replace('    if (mode == "guards") {', '''    if (mode == "guards") {
        for (unsigned test = 0; test < 8; ++test) {
            experimentExiRiUart = test != 0;
            context.msr = test == 1 ? 0x2031 : 0x2032;
            const auto before = std::array<uint32_t, 6>{hw::experimentExiMaskState[0], hw::experimentExiMaskState[1],
                hw::experimentExiMaskState[2], hw::experimentExiTransfer.control, hw::experimentExiTransfer.data, hw::pi_intsr.load()};
            bool refused = false;
            try {
                if (test >= 5) {
                    experiment_getid_write32(context, test == 7 ? 0xcd006814 : 0xcd006800,
                        test == 5 ? 0x200 : test == 6 ? 0x130 : 0x80, test == 7 ? 0x802177d8 : 0x8020e3ec);
                } else {
                    experiment_getid_read32(context, test == 3 ? 0xcd006820 : test == 4 ? 0xcc003000 : 0xcd006800,
                        test == 2 ? 0x80100000 : 0x8020e3c0);
                }
            } catch (const std::runtime_error&) { refused = true; }
            const auto after = std::array<uint32_t, 6>{hw::experimentExiMaskState[0], hw::experimentExiMaskState[1],
                hw::experimentExiMaskState[2], hw::experimentExiTransfer.control, hw::experimentExiTransfer.data, hw::pi_intsr.load()};
            if (!refused || before != after) { return 13; }
        }
        experimentExiRiUart = true;
        std::cout << "RI_UART_GUARDS 8\\n";''')
host = output / 'uart-ri-host.cpp'
host.write_text('#include "memory_protection_frontend.h"\n#include "sram_frontend.h"\n' + body + host_body)
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    experiment / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
    runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'uart-ri-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(experiment / 'memory_protection_frontend.h'), '-DSHSM_SI_EXTERNAL_DELIVERY',
    '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-I', str(output), '-I', str(experiment),
    '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[r['object'] for r in records], '-o', str(exe)],
    capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2500:]
results = {}
for mode in ('normal', 'lost', 'full', 'guards'):
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', mode], capture_output=True, text=True, timeout=30)
    (output / (mode + '.log')).write_text(result.stdout + result.stderr)
    results[mode] = {'returnCode': result.returncode, 'logSha256': sha(output / (mode + '.log'))}
    print(mode, result.returncode, (result.stdout + result.stderr)[-180:])
(output / 'build.json').write_text(json.dumps({'result': 'UART_RI_NATIVE_REQUIRES_COMPARISON', 'builderSha256': sha(Path(__file__)),
    'records': records, 'sourceHashes': {str(path): sha(path) for path in sources}, 'results': results,
    'headerHashes': {str(path): sha(path) for path in experiment.glob('*.h')}, 'executableSha256': sha(exe),
    'baseBootSha256': sha(base / 'boot.json')}, indent=2) + '\n')
assert results['normal']['returnCode'] == 0
