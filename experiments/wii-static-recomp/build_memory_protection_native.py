"""Run the whole compiled memory-protection procedure against the owned DOL."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
base = private / 'mass-audio-init-boot'
output = private / 'memory-protection-native'
output.mkdir(exist_ok=True)
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_memory_protection_dolphin.py')], check=True)
build = json.loads((base / 'boot.json').read_text())
headers = {str(path): sha(path) for path in experiment.glob('*.h')}
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
layout = struct.unpack('>64I', dol[:256])
def word_at(address):
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    return struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0]
plans = {}
for name, start, size in [('Mem1', 0x80218070, 128), ('Mem2', 0x802180f0, 212)]:
    registers = [0] * 32
    steps = []
    for site in range(start, start + size, 4):
        word = word_at(site)
        primary, rt, ra = word >> 26, (word >> 21) & 31, (word >> 16) & 31
        imm = word & 65535
        if imm & 32768:
            imm -= 65536
        if primary in (14, 15):
            registers[rt] = ((registers[ra] if ra else 0) + (imm if primary == 14 else imm << 16)) & 0xffffffff
        elif primary == 31 and (word >> 1) & 1023 == 467:
            spr = ((word >> 16) & 31) | ((word >> 6) & 992)
            if 528 <= spr < 544 or 560 <= spr < 576:
                relative = spr - (528 if spr < 544 else 560)
                steps.append([site, relative < 8, relative // 2 % 4 + (4 if spr >= 560 else 0), bool(relative % 2), registers[rt]])
    assert len(steps) == (12 if name == 'Mem1' else 20)
    plans[name] = steps
plan_header = output / 'memory-protection-bat-plan.h'
plan_header.write_text('\n'.join('inline constexpr std::array<MemoryProtectionBatStep, ' + str(len(steps)) + '> memoryProtection' + name + 'Plan{{\n' +
    ',\n'.join('    {' + ', '.join(str(v).lower() if isinstance(v, bool) else hex(v) for v in row) + '}' for row in steps) + '\n}};'
    for name, steps in plans.items()) + '\n')
for name in ('mass_boot.cpp', 'loader-bat-seed.h'):
    (output / name).write_bytes((base / name).read_bytes())
records, changes = [], []
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
            if site in (0x802186ac, 0x802186bc) and 'bat_memory_write16(ctx,' in line:
                line = line.replace('bat_memory_write16', 'experiment_memory_protection_write16').replace('); //', f', 0x{site:08x}); //')
            elif site == 0x802176e4 and 'experiment_mi_mask_boot_write16' in line:
                line = line.replace('experiment_mi_mask_boot_write16', 'experiment_memory_protection_mask_write')
            elif site in {step[0] for steps in plans.values() for step in steps} and 'experiment_write_bat(ctx,' in line:
                line = line.replace('experiment_write_bat', 'experiment_memory_protection_bat_write').replace(');', f', 0x{site:08x});')
            elif site in (0x80218504, 0x802180ec, 0x802181c0) and line == '    {\n':
                guard = 'experiment_memory_protection_real_enter(ctx)' if site == 0x80218504 else f'experiment_memory_protection_real_return(ctx, 0x{site:08x})'
                line = '    nwii::runtime::' + guard + ';\n' + line
            if line != before:
                changes.append({'site': site, 'before': before, 'after': line})
                lines[index] = line
        assert len(changes) == 38
        source = output / row['file']
        source.write_text(''.join(lines))
        obj = output / (row['file'] + '.o')
        result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
            '-include', str(experiment / 'memory_protection_frontend.h'), '-I', str(runtime / 'include'),
            '-I', str(private / 'mass-current'), '-I', str(output), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
        (output / 'compile.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        record.update(source=str(source), sourceSha256=sha(source), object=str(obj), objectSha256=sha(obj))
    records.append(record)
host = output / 'mi-host.cpp'
body = (experiment / 'exi_getid_host.cpp').read_text()
body = body[:body.index('int main(int argc, char** argv)')]
body = body.replace('    if (context.inst_count > 100000)',
    '    if (context.pc == 0x807f0000) { throw std::runtime_error("MI oracle return sentinel"); }\n    if (context.inst_count > 1000000)')
host.write_text('#include "memory_protection_frontend.h"\n#include "sram_frontend.h"\n' + body + (experiment / 'memory_protection_host.cpp').read_text())
sources = [host, experiment / 'processor_adapter.cpp', experiment / 'ipc_reset_backend.cpp', experiment / 'ai_mask_backend.cpp',
    experiment / 'dsp_startup_backend.cpp', runtime / 'src/core/loader.cpp', runtime / 'src/hw/hw_pi.cpp',
    runtime / 'src/hw/mmio_dispatcher.cpp', runtime / 'src/core/event_scheduler.cpp']
exe = output / 'memory-protection-probe'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', 'bit',
    '-include', str(experiment / 'memory_protection_frontend.h'), '-DSHSM_SI_EXTERNAL_DELIVERY',
    '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER', '-I', str(output), '-I', str(experiment),
    '-I', str(private / 'mass-current'), '-I', str(runtime / 'include'), '-I', str(runtime / 'src/hw'),
    '-I', str(runtime.parent / 'nWiiAnalyzer/include'), *map(str, sources), *[row['object'] for row in records], '-o', str(exe)],
    capture_output=True, text=True, timeout=180)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
(output / 'native.log').write_text(result.stdout + result.stderr)
(output / 'build.json').write_text(json.dumps({'result': 'MEMORY_PROTECTION_NATIVE_REQUIRES_COMPARISON', 'records': records,
    'changes': changes, 'builderSha256': sha(Path(__file__)), 'baseSha256': sha(base / 'boot.json'), 'returnCode': result.returncode,
    'sourceHashes': {str(path): sha(path) for path in sources}, 'executableSha256': sha(exe), 'headerHashes': headers,
    'planHeaderSha256': sha(plan_header), 'plans': plans, 'originalSha256': hashlib.sha256(dol).hexdigest()}, indent=2) + '\n')
print(result.stdout[-600:] + result.stderr)
assert result.returncode == 0
guard = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'], capture_output=True, text=True, timeout=30)
(output / 'guards.log').write_text(guard.stdout + guard.stderr)
assert guard.returncode == 0 and guard.stdout == 'MI_GUARDS 26\n' and not guard.stderr, guard.stdout + guard.stderr
