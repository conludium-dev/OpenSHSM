"""Incremental ICE lowering over the verified translated FPSCR module; preserve original control flow."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess

base = Path('work/private-game/static-recomp/mass-fpscr-translated')
output = Path('work/private-game/static-recomp/mass-icache')
output.mkdir(exist_ok=True)
experiment = Path('experiments/wii-static-recomp')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
module = Path('work/private-game/static-recomp/mass-current')
lowering = json.loads((base / 'lowering.json').read_text())
assert lowering['initialMsr'] == 0x30
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
changes, records, objects = [], [], []
for original in lowering['records']:
    name = original['file']
    directory = Path(original['directory'])
    source = directory / name
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original['sourceSha256']
    assert hashlib.sha256((directory / (name + '.o')).read_bytes()).hexdigest() == original['objectSha256']
    lines = source.read_text().splitlines(True)
    modified = False
    for index, line in enumerate(lines):
        match = re.search(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', line)
        if not match:
            continue
        address, opcode = [int(value, 16) for value in match.groups()]
        if opcode >> 26 != 31 or ((opcode >> 1) & 1023) != 467:
            continue
        spr = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
        if spr != 1008:
            continue
        section = next(section for section in range(18) if header[18 + section] <= address < header[18 + section] + header[36 + section])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        register = (opcode >> 21) & 31
        prior = lines[index + 1]
        assert prior.strip() == f'nwii::runtime::experiment_write_hid0(ctx, ctx.gpr[{register}]);'
        replacement = f'    nwii::runtime::experiment_write_hid0_icache(ctx, ctx.gpr[{register}]);\n'
        lines[index + 1] = replacement
        modified = True
        changes.append({'file': name, 'address': hex(address), 'opcode': hex(opcode), 'register': register,
                        'priorLowering': prior.strip(), 'adapterLowering': replacement.strip()})
    if modified:
        source = output / name
        source.write_text(''.join(lines))
        result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', str(experiment / 'icache_adapter.h'),
                                 '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(module), '-c', str(source),
                                 '-o', str(output / (name + '.o'))], capture_output=True, text=True, timeout=180)
        (output / (name + '.build.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        directory = output
    objects.append(str(directory / (name + '.o')))
    records.append({'file': name, 'directory': str(directory), 'inputDirectory': original['directory'],
                    'inputSha256': original['sourceSha256'], 'modified': modified,
                    'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'objectSha256': hashlib.sha256((directory / (name + '.o')).read_bytes()).hexdigest()})
report = {'result': 'PASS', 'records': records, 'changes': changes,
          'baseLoweringSha256': hashlib.sha256((base / 'lowering.json').read_bytes()).hexdigest(),
          'adapterSha256': hashlib.sha256((experiment / 'icache_adapter.h').read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(output / 'lowering.json').write_text(json.dumps(report, indent=2) + '\n')
policy = output / 'boot-quarantine.tsv'
policy.write_bytes((base / 'boot-quarantine.tsv').read_bytes())
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
                         '-DSHSM_BOOT_INITIAL_MSR=0x30', '-I', str(module), '-I', str(upstream / 'nWiiRuntime/include'),
                         '-I', str(upstream / 'nWiiAnalyzer/include'), str(experiment / 'icache_boot.cpp'),
                         str(experiment / 'processor_adapter.cpp'), str(upstream / 'nWiiRuntime/src/core/loader.cpp'),
                         *objects, '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'boot-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout, (result.returncode, result.stdout[-3000:], result.stderr[-1000:])
report = {'result': 'BLOCKED_AT_ORIGINAL_BOOT', 'stdout': result.stdout, 'exitCode': result.returncode,
          'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'wrapperSha256': hashlib.sha256((experiment / 'icache_boot.cpp').read_bytes()).hexdigest(),
          'baseWrapperSha256': hashlib.sha256((experiment / 'mass_boot.cpp').read_bytes()).hexdigest(),
          'fpscrWrapperSha256': hashlib.sha256((experiment / 'fpscr_boot.cpp').read_bytes()).hexdigest(),
          'policySha256': hashlib.sha256(policy.read_bytes()).hexdigest()}
(output / 'boot.json').write_text(json.dumps(report, indent=2) + '\n')
print('Incremental ICE lowering:', len(changes), 'sites;', sum(record['modified'] for record in records), 'batches', flush=True)
print(result.stdout, flush=True)
