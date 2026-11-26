"""Compile original SI query setup/completion/callback with measured MMIO routing."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import struct

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'si-query-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_si_query_dolphin.py')], check=True)
metadata_path = private / 'exi-getid-native/execution.json'
metadata = json.loads(metadata_path.read_text())
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
records = []
for row in metadata['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] in ('output_62.cpp', 'output_63.cpp'):
        source_input = Path(row['source'])
        lines = source_input.read_text().splitlines(True)
        changes = []
        for index, line in enumerate(lines[:-1]):
            marker = re.fullmatch(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n', line)
            if not marker:
                continue
            following = lines[index + 1]
            if 'experiment_getid_read32(' not in following and 'experiment_getid_write32(' not in following:
                continue
            address, opcode = (int(value, 16) for value in marker.groups())
            section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
            assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
            replacement = following.replace('experiment_getid_read32(', 'experiment_si_query_read32(').replace('experiment_getid_write32(', 'experiment_si_query_write32(')
            call_start = replacement.index('experiment_si_query_')
            call_end = replacement.index(');', call_start)
            if not replacement[:call_end].endswith(', ' + hex(address)):
                replacement = replacement[:call_end] + ', ' + hex(address) + replacement[call_end:]
            assert replacement != following
            changes.append({'instruction': address, 'opcode': opcode, 'before': following, 'after': replacement})
            lines[index + 1] = replacement
        source = output / row['file']
        source.write_text(''.join(lines))
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', str(experiment / 'si_query_frontend.h'),
            '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / (row['file'] + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        record.update({'source': str(source), 'sourceSha256': sha(source), 'object': str(obj), 'objectSha256': sha(obj),
            'inputSource': str(source_input), 'inputSourceSha256': sha(source_input), 'changes': changes})
    records.append(record)
(output / 'loader-bat-seed.h').write_bytes((private / 'exi-getid-native/loader-bat-seed.h').read_bytes())
host = output / 'si-query-host.cpp'
body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')
host.write_text('#include "si_query_frontend.h"\n' + body + '\n' + (experiment / 'si_query_host.cpp').read_text())
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp', runtime / 'src/core/loader.cpp',
    runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'si-query-probe'
command = ['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
    '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in records], '-o', str(exe)]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
(output / 'build.json').write_text(json.dumps({'result': 'SI_QUERY_COMPILED_EXECUTION_REQUIRES_VERIFICATION', 'returnCode': result.returncode,
    'builderSha256': sha(Path(__file__)), 'records': records, 'baseExecutionSha256': sha(metadata_path), 'executableSha256': sha(exe),
    'oracleSha256': sha(private / 'dolphin-si-query-callback/comparison.json'), 'sourceHashes': {str(path): sha(path) for path in sources},
    'backendSha256': sha(experiment / 'si_idle_backend.h'), 'queryBackendSha256': sha(experiment / 'si_query_backend.h'),
    'frontendSha256': sha(experiment / 'si_query_frontend.h')}, indent=2) + '\n')
print(result.stdout[-1600:] + result.stderr)
assert result.returncode == 0, 'Whole native SI query fixture has not completed'
