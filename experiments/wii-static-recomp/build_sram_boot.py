"""Extend the existing guarded SI boot with verified SRAM command and DMA."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-si-query-boot'
output = private / 'mass-sram-boot'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_sram_native.py')], check=True)
proof = private / 'sram-native/comparison.json'
metadata_path = base / 'boot.json'
metadata = json.loads(metadata_path.read_text())
assert metadata['executableSha256'] == sha(base / 'openshsm-mass-boot')
for name in ('mass_boot.cpp', 'loader-bat-seed.h', 'fp64-template-probe.h', 'mutable-template-probe.h', 'hw_vi-clock.inc', 'vi-clock-backend.cpp'):
    (output / name).write_bytes((base / name).read_bytes())
entry = output / 'mass_boot.cpp'
before = '    nwii::runtime::ProcessorContext context;\n    if (std::getenv("SHSM_SI_IDLE_REPLAY"))'
after = before.replace('\n    if', '\n    nwii::runtime::experiment_sram_attach_memory(context);\n    if')
text = entry.read_text()
assert text.count(before) == 1
entry.write_text(text.replace(before, after))
records = []
for row in metadata['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] in ('output_62.cpp', 'output_63.cpp'):
        source = output / row['file']
        source.write_bytes(Path(row['source']).read_bytes())
        obj = output / (row['file'] + '.o')
        command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'sram_frontend.h'), '-include', str(experiment / 'si_query_frontend.h'),
            '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        (output / (row['file'] + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        record.update({'source': str(source), 'sourceSha256': sha(source), 'object': str(obj), 'objectSha256': sha(obj),
            'inputSource': row['source'], 'inputSourceSha256': row['sourceSha256']})
    records.append(record)
wrapper = output / 'boot-wrapper.cpp'
body = '#include "sram_frontend.h"\n' + (base / 'boot-wrapper.cpp').read_text()
before_call = '    const int result = original_boot_main(argc, argv);'
before_settings = '''    if (argc != 4 && argc != 5) { return 2; }
    if (argc == 5 && std::string(argv[4]) != "--no-sram") { return 2; }
    auto& sram = nwii::runtime::hw::experimentExiTransfer;
    std::ifstream settings(argv[3], std::ios::binary);
    if (!settings.read(reinterpret_cast<char*>(sram.sramResponse.data()), sram.sramResponse.size()) || settings.peek() != EOF) { return 4; }
    sram.sramAllowed = argc == 4;
'''
after_call = '    const int result = original_boot_main(3, argv);\n    std::cout << "BOOT_SRAM phase=" << sram.phase << " address=" << std::hex << sram.dmaAddress << " length=" << sram.dmaLength << " control=" << sram.control << std::dec << "\\n";'
assert body.count(before_call) == 1
body = body.replace(before_call, before_settings + after_call)
wrapper.write_text(body)
sources = [wrapper, output / 'vi-clock-backend.cpp', experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'openshsm-mass-boot'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_SI_EXTERNAL_DELIVERY', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-DSHSM_BOOT_INITIAL_MSR=0x30',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in records], '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
policy = private / 'mass-ni-guard/boot-quarantine.tsv'
settings = private / 'sram-native/settings.bin'
results = {}
for mode in ('live', 'scripted', 'disabled'):
    environment = dict(os.environ)
    environment.pop('SHSM_SI_IDLE_REPLAY', None)
    if mode != 'live':
        environment['SHSM_SI_IDLE_REPLAY'] = '1'
    arguments = [str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy), str(settings)]
    if mode == 'disabled':
        arguments.append('--no-sram')
    result = subprocess.run(arguments,
        env=environment, capture_output=True, text=True, timeout=30)
    (output / (mode + '-boot.log')).write_text(result.stdout + result.stderr)
    results[mode] = {'returnCode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    print(mode + ': ' + result.stdout[-1800:] + result.stderr)
header_names = ('sram_frontend.h', 'exi_getid_backend.h', 'exi_getid_frontend.h', 'si_query_frontend.h', 'boot_poll.h', 'si_external_delivery.h', 'bat_memory_frontend.h')
(output / 'boot.json').write_text(json.dumps({'result': 'SRAM_BOOT_REQUIRES_NEXT_BOUNDARY_AUDIT', 'results': results,
    'builderSha256': sha(Path(__file__)), 'baseBootSha256': sha(metadata_path), 'nativeProofSha256': sha(proof),
    'executableSha256': sha(exe), 'records': records, 'sourceHashes': {str(path): sha(path) for path in sources},
    'headerHashes': {name: sha(experiment / name) for name in header_names}, 'entrySha256': sha(entry),
    'settingsSha256': sha(settings), 'policySha256': sha(policy), 'entryBefore': before, 'entryAfter': after,
    'wrapperBefore': before_call, 'wrapperAfter': before_settings + after_call,
    'limits': ['Existing guarded boot with private emulator-generated SRAM reference settings, not an import/release dependency.',
        'Live clock and scripted replay distinct; next unsupported state remains refused. No game-launch/frame claim.']}, indent=2) + '\n')
assert all(result['returnCode'] == 7 and 'BOOT_BOUNDARY' in result['stdout'] for result in results.values())
