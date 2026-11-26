"""Reuse the compiled module to execute original GetID on a measured bus profile."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-exi-select-boot'
output = private / 'exi-getid-native'
output.mkdir(exist_ok=True)
module = private / 'mass-current'
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_exi_getid_dolphin.py')], check=True)
subprocess.run(['python3', str(experiment / 'verify_di_config_dolphin.py')], check=True)
metadata = json.loads((base / 'lowering.json').read_text())
(output / 'loader-bat-seed.h').write_bytes((base / 'loader-bat-seed.h').read_bytes())
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
objects, records = [], []
for record in metadata['records']:
    source = Path(record['directory']) / record['file']
    obj = Path(str(source) + '.o')
    assert sha(source) == record['sourceSha256'] and sha(obj) == record['objectSha256']
    input_source = source
    changed = record['file'] in ('output_62.cpp', 'output_63.cpp')
    if changed:
        text = source.read_text()
        markers = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', text)
        for address, opcode in markers:
            address = int(address, 16)
            section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
            assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == int(opcode, 16)
        text = text.replace('nwii::runtime::bat_memory_read32(', 'nwii::runtime::experiment_getid_read32(')
        text = text.replace('nwii::runtime::bat_memory_write32(', 'nwii::runtime::experiment_getid_write32(')
        for name in ('exi_init_boot', 'exi_select_boot', 'exi_boot', 'exi_next'):
            text = text.replace(f'nwii::runtime::experiment_{name}_read32(', 'nwii::runtime::experiment_getid_read32(')
            text = text.replace(f'nwii::runtime::experiment_{name}_write32(', 'nwii::runtime::experiment_getid_write32(')
        text = text.replace('nwii::runtime::experiment_set_mask_pi_write32(', 'nwii::runtime::experiment_getid_write32(')
        source = output / record['file']
        source.write_text(text)
        obj = Path(str(source) + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', str(experiment / 'exi_getid_frontend.h'),
                                 '-I', str(runtime / 'include'), '-I', str(module), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / (record['file'] + '.build.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
    objects.append(str(obj))
    records.append({'file': record['file'], 'inputSource': str(input_source), 'inputSha256': sha(input_source),
                    'source': str(source), 'sourceSha256': sha(source), 'object': str(obj), 'objectSha256': sha(obj), 'changed': changed})
sources = [experiment / 'exi_getid_host.cpp', experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp',
           experiment / 'ai_mask_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
           runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'exi-getid-probe'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
           '-I', str(output), '-I', str(experiment), '-I', str(module), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
           '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *objects, '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), str(dol_path)], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
report = {'result': 'COMPILED_GETID_TRANSACTION_UNVERIFIED', 'returnCode': result.returncode, 'records': records,
          'builderSha256': sha(Path(__file__)), 'baseLoweringSha256': sha(base / 'lowering.json'),
          'oracleSha256': sha(private / 'dolphin-exi-getid/comparison.json'), 'diOracleSha256': sha(private / 'dolphin-di-config/comparison.json'), 'executableSha256': sha(exe),
          'sourceHashes': {str(path): sha(path) for path in sources},
          'headerHashes': {name: sha(experiment / name) for name in ('exi_getid_frontend.h', 'exi_getid_backend.h', 'exi_mask_backend.h')},
          'stdout': result.stdout, 'stderr': result.stderr}
(output / 'execution.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout[-3000:] + result.stderr)
assert result.returncode == 0, 'Whole native GetID has not completed'
