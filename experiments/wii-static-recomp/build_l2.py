"""Incremental L2CR register model; physical L2 effects remain unverified."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
base = Path('work/private-game/static-recomp/mass-dcache')
output = Path('work/private-game/static-recomp/mass-l2')
output.mkdir(exist_ok=True)
module = Path('work/private-game/static-recomp/mass-current')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
lowering = json.loads((base / 'lowering.json').read_text())
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', original[:256])
objects, records, changes = [], [], []
for record in lowering['records']:
    source = Path(record['directory']) / record['file']
    obj = Path(str(source) + '.o')
    assert sha(source) == record['sourceSha256'] and sha(obj) == record['objectSha256']
    lines = source.read_text().splitlines(True)
    count = 0
    for index, line in enumerate(lines):
        match = re.search(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', line)
        if not match:
            continue
        address, opcode = (int(value, 16) for value in match.groups())
        if opcode >> 26 != 31 or ((opcode >> 1) & 1023) not in (339, 467):
            continue
        if ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5) != 1017:
            continue
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', original, header[section] + address - header[18 + section])[0] == opcode
        register = (opcode >> 21) & 31
        before = lines[index + 1]
        if ((opcode >> 1) & 1023) == 339:
            assert before.strip() == f'ctx.gpr[{register}] = 0; // mfspr L2CR'
            after = f'    ctx.gpr[{register}] = nwii::runtime::experiment_read_l2cr(ctx);\n'
        else:
            assert before.strip() == '// unhandled mtspr 1017'
            after = f'    nwii::runtime::experiment_write_l2cr(ctx, ctx.gpr[{register}]);\n'
        lines[index + 1] = after
        changes.append({'file': record['file'], 'line': index + 2, 'address': hex(address), 'opcode': hex(opcode),
                        'before': before, 'after': after})
        count += 1
    if count:
        source = output / record['file']
        source.write_text(''.join(lines))
        obj = Path(str(source) + '.o')
        result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', str(experiment / 'l2_adapter.h'),
                                 '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(module), '-c', str(source), '-o', str(obj)],
                                capture_output=True, text=True, timeout=180)
        (output / (record['file'] + '.build.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
    objects.append(str(obj))
    records.append({'file': record['file'], 'directory': str(source.parent), 'sourceSha256': sha(source),
                    'objectSha256': sha(obj), 'changedSites': count})
assert changes
wrapper = output / 'boot-wrapper.cpp'
wrapper.write_text((experiment / 'dcache_boot.cpp').read_text().replace('#include "dcache_adapter.h"', '#include "l2_adapter.h"')
                   .replace('#define ProcessorContext MemoryContext', '#define ProcessorContext L2Context')
                   .replace('#include "mass_boot.cpp"', '#define process_pending_callbacks original_scheduler\n#include "mass_boot.cpp"')
                   .replace('#undef main', '#undef main\n#undef process_pending_callbacks')
                   .replace('void trace_call(uint32_t address, CPUContext& context)', 'void l2_snapshot(uint32_t address, CPUContext& context)')
                   .replace('    original_trace_call(address, context);', '')
                   + '\nnamespace nwii::runtime {\nvoid trace_call(uint32_t address, CPUContext& context) {\n'
                   + '    l2_snapshot(address, context);\n    original_trace_call(address, context);\n}\n'
                   + 'bool process_pending_callbacks(CPUContext& context) {\n'
                   + '    l2_snapshot(context.pc, context);\n    return original_scheduler(context);\n}\n}\n')
policy = output / 'boot-quarantine.tsv'
prior_policy = Path('work/private-game/static-recomp/mass-icache/boot-quarantine.tsv').read_text().splitlines(True)
removed = [line for line in prior_policy if line.startswith(('802106C0\t', '802106D0\t'))]
assert removed == ['802106C0\tUNVERIFIED_PROCESSOR_REGISTER_1017\n', '802106D0\t//_unhandled\n']
policy.write_text(''.join(line for line in prior_policy if line not in removed))
report = {'result': 'L2_REGISTER_MODEL_NOT_HARDWARE_CACHE', 'records': records, 'changes': changes,
          'baseLoweringSha256': sha(base / 'lowering.json'), 'adapterSha256': sha(experiment / 'l2_adapter.h'),
          'scriptSha256': sha(Path(__file__)), 'wrapperSha256': sha(wrapper), 'removedPolicyEntries': removed}
(output / 'lowering.json').write_text(json.dumps(report, indent=2) + '\n')
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
                         '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(experiment), '-I', str(module), '-I', str(upstream / 'nWiiRuntime/include'),
                         '-I', str(upstream / 'nWiiAnalyzer/include'), str(wrapper), str(experiment / 'processor_adapter.cpp'),
                         str(upstream / 'nWiiRuntime/src/core/loader.cpp'), *objects, '-o', str(exe)],
                        capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout
(output / 'boot.json').write_text(json.dumps({'result': 'L2_MODEL_BOOT_ENDPOINT_UNVERIFIED', 'stdout': result.stdout,
                                            'executableSha256': sha(exe), 'loweringSha256': sha(output / 'lowering.json'),
                                            'policySha256': sha(policy)}, indent=2) + '\n')
print(f'L2 register lowering:{len(changes)}sites; boot endpoint requires independent check', flush=True)
print(result.stdout[-1800:], flush=True)
