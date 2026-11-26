"""Connect the original FPU vector/handler/retry to the existing compiled dispatcher."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-ai-clock-boot'
output = private / 'fpu-first-use-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_fpu_lazy_dolphin.py')], check=True)
build = json.loads((base / 'boot.json').read_text())
for name in ('mass_boot.cpp', 'loader-bat-seed.h'):
    (output / name).write_bytes((base / name).read_bytes())
records = []
changes = []
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    record = dict(row)
    if row['file'] in ('output_1.cpp', 'output_63.cpp', 'main_output.cpp'):
        original = Path(row['source']).read_text()
        text = original
        if row['file'] == 'output_1.cpp':
            start = text.index('void func_80005F34(')
            end = text.index('\nvoid func_', start + 1)
            def transfer(match):
                address, opcode = int(match[1], 16), int(match[2], 16)
                section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
                assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode == int(match[3], 16)
                after = match[0].replace('nwii::runtime::experiment_fp64_transfer(ctx, ' + match[3] + ');',
                    'if (nwii::runtime::experiment_fpu_first_use_transfer(ctx, ' + match[3] + ', ' + hex(address) + ')) { return; }')
                changes.append({'file': row['file'], 'before': match[0], 'after': after, 'instruction': address, 'opcode': opcode})
                return after
            block = re.sub(r'    // 0x([0-9A-F]{8}): ([0-9A-F]{8})\n    nwii::runtime::experiment_fp64_transfer\(ctx, (0x[0-9a-f]+)\);', transfer, text[start:end])
            text = text[:start] + block + text[end:]
        elif row['file'] == 'output_63.cpp':
            before = '    if (bat_memory_read32(ctx, 0x568) != 0x38600004) { throw std::runtime_error("Unverified relocated vector ID"); }\n    ctx.gpr[3] = 4;'
            after = '    {\n        const bool fpu = nwii::runtime::bat_context(ctx).exceptionVector == 7;\n        if (bat_memory_read32(ctx, fpu ? 0x868 : 0x568) != (fpu ? 0x38600007 : 0x38600004)) { throw std::runtime_error("Unverified relocated vector ID"); }\n        ctx.gpr[3] = fpu ? 7 : 4;\n    }'
            assert text.count(before) == 1
            text = text.replace(before, after)
            changes.append({'file': row['file'], 'before': before, 'after': after})
        else:
            before = '            case 0x80005F34: func_80005F34(ctx); break;'
            after = before + '\n            case 0x800060F4: func_80005F34(ctx); break;'
            assert text.count(before) == 1
            text = text.replace(before, after)
            changes.append({'file': row['file'], 'before': before, 'after': after})
        assert text != original
        source = output / row['file']
        source.write_text(text)
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'ai_clock_profile.h'), '-include', str(experiment / 'fpu_first_use.h'),
            '-I', str(runtime / 'include'), '-I', str(private / 'mass-current'), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / (row['file'] + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-2000:]
        record.update({'source': str(source), 'sourceSha256': sha(source), 'object': str(obj), 'objectSha256': sha(obj),
            'inputSource': row['source'], 'inputSourceSha256': row['sourceSha256']})
    records.append(record)
host = output / 'fpu-host.cpp'
body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')
body = body.replace('    if (context.inst_count > 100000)', '    if (context.pc == 0x807f0000) { throw std::runtime_error("FPU oracle return sentinel"); }\n    if (context.inst_count > 100000)')
host.write_text('#include "ai_clock_profile.h"\n#include "sram_frontend.h"\n#include "fpu_first_use.h"\n' + body + '\n' + (experiment / 'fpu_first_use_host.cpp').read_text())
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp', runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/hw/hw_dsp.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'fpu-first-use-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_SI_EXTERNAL_DELIVERY',
    '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-I', str(output), '-I', str(experiment), '-I', str(private / 'mass-current'),
    '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'), '-I', str(runtime.parent / 'nWiiAnalyzer/include'),
    *map(str, sources), *[row['object'] for row in records], '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
(output / 'build.json').write_text(json.dumps({'result': 'FPU_NATIVE_REQUIRES_COMPARISON', 'returnCode': result.returncode,
    'builderSha256': sha(Path(__file__)), 'baseBootSha256': sha(base / 'boot.json'), 'records': records, 'changes': changes,
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe),
    'headerHashes': {name: sha(experiment / name) for name in ('fpu_first_use.h', 'bat_context.h', 'bat_memory_frontend.h', 'si_external_delivery.h')},
    'oracleSha256': sha(private / 'dolphin-fpu-lazy/comparison.json')}, indent=2) + '\n')
print(result.stdout[-1000:] + result.stderr)
assert result.returncode == 0
