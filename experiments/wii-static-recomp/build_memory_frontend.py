"""Route the entire existing generated module through one experimental cache-aware memory frontend."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import re
import subprocess

base = Path('work/private-game/static-recomp/mass-icache')
output = Path('work/private-game/static-recomp/mass-memory')
output.mkdir(exist_ok=True)
experiment = Path('experiments/wii-static-recomp')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
module = Path('work/private-game/static-recomp/mass-current')
metadata = json.loads((base / 'lowering.json').read_text())
allowed = {'read8', 'read16', 'read32', 'read64', 'read_f32', 'read_f64', 'write8', 'write16', 'write32', 'write64', 'write_f32', 'write_f64'}

def compile_record(record):
    directory = Path(record['directory'])
    source = directory / record['file']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['sourceSha256']
    text = source.read_text()
    changes = []
    lines = text.splitlines(True)
    opcode = None
    for index, line in enumerate(lines):
        match = re.search(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', line)
        if match:
            opcode = int(match[2], 16)
        updated = line
        for operation in set(re.findall(r'ctx\.mmu\.([A-Za-z_0-9]+)\(', line)):
            assert operation in allowed, (record['file'], operation)
            updated = updated.replace('ctx.mmu.' + operation + '(', 'nwii::runtime::memory_' + operation + '(ctx, ')
        for operation in ('load', 'store'):
            updated = updated.replace('ctx.psq_' + operation + '(', 'nwii::runtime::memory_psq_' + operation + '(ctx, ')
        if opcode is not None and opcode >> 26 == 31 and ((opcode >> 1) & 1023) in (54, 86, 470, 278, 246) and line.strip() == '// sync/cache instruction':
            ra, rb, operation = (opcode >> 16) & 31, (opcode >> 11) & 31, (opcode >> 1) & 1023
            effective = f'ctx.gpr[{ra}] + ctx.gpr[{rb}]' if ra else f'ctx.gpr[{rb}]'
            updated = f'    nwii::runtime::memory_cache_operation(ctx, {effective}, {operation});\n'
        if updated != line:
            changes.append({'line': index + 1, 'before': line.rstrip(), 'after': updated.rstrip()})
            lines[index] = updated
    result_text = ''.join(lines)
    assert not re.search(r'ctx\.mmu\.|ctx\.psq_(?:load|store)\(', result_text)
    target = output / record['file']
    target.write_text(result_text)
    obj = output / (record['file'] + '.o')
    command = ['clang++', '-std=c++20', '-O0', '-include', str(experiment / 'memory_frontend.h'),
               '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(module), '-c', str(target), '-o', str(obj)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    (output / (record['file'] + '.build.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    print('Compiled memory frontend', record['file'], flush=True)
    return {'file': record['file'], 'inputDirectory': record['directory'], 'inputSha256': record['sourceSha256'],
            'sourceSha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'objectSha256': hashlib.sha256(obj.read_bytes()).hexdigest(),
            'changes': changes}

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    records = list(pool.map(compile_record, metadata['records']))
report = {'result': 'COMPILED_NOT_BOOT_VERIFIED', 'records': records, 'filesCompiled': len(records),
          'memoryRoutingLines': sum(len(record['changes']) for record in records),
          'baseLoweringSha256': hashlib.sha256((base / 'lowering.json').read_bytes()).hexdigest(),
          'headerSha256': hashlib.sha256((experiment / 'memory_frontend.h').read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'limits': ['Every generated direct MMU/paired memory call routed; no new original-game function body or resource store.',
                     'Quantized paired formats abort pending independent verification; float format supported.',
                     'DCE boot gate remains closed; compiled objects alone do not establish original execution or cache fidelity.']}
(output / 'lowering.json').write_text(json.dumps(report, indent=2) + '\n')
print('COMPILED ONLY:', len(records), 'files;', report['memoryRoutingLines'], 'routed lines; DCE/game acceptance pending')
