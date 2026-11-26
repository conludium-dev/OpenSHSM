"""Apply opcode-verified mtfsf lowering over the existing cache/module snapshot."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--translated-fixture', action='store_true')
args = parser.parse_args()
base = Path('work/private-game/static-recomp/mass-current')
cache = Path('work/private-game/static-recomp/mass-cache')
output = Path('work/private-game/static-recomp/mass-fpscr-translated' if args.translated_fixture else 'work/private-game/static-recomp/mass-fpscr')
output.mkdir(exist_ok=True)
experiment = Path('experiments/wii-static-recomp')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
objects = json.loads((base / 'objects.json').read_text())
cache_records = {record['file']: record for record in json.loads((cache / 'lowering.json').read_text())['files']}
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', dol[:256])
changes, records, paths, quarantine = [], [], [], []
for original in objects['records']:
    name = original['file']
    selected = cache_records.get(name, original)
    directory = cache if name in cache_records else base
    source = directory / name
    assert hashlib.sha256(source.read_bytes()).hexdigest() == selected['sourceSha256']
    assert hashlib.sha256((directory / (name + '.o')).read_bytes()).hexdigest() == selected['objectSha256']
    lines = source.read_text().splitlines(True)
    modified = False
    for index, line in enumerate(lines):
        match = re.search(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', line)
        if not match:
            continue
        address, opcode = [int(value, 16) for value in match.groups()]
        if opcode >> 26 != 63 or ((opcode >> 1) & 1023) != 711:
            continue
        section = next(section for section in range(18) if header[18 + section] <= address < header[18 + section] + header[36 + section])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == opcode
        prior = lines[index + 1]
        assert prior.strip() == '// mtfsf stub (ignore FPSCR write)'
        replacement = f'    nwii::runtime::experiment_mtfsf(ctx, 0x{opcode:08X});\n'
        lines[index + 1] = replacement
        modified = True
        changes.append({'file': name, 'address': hex(address), 'opcode': hex(opcode),
                        'fields': (opcode >> 17) & 255, 'register': (opcode >> 11) & 31, 'record': bool(opcode & 1),
                        'priorLowering': prior.strip(), 'adapterLowering': replacement.strip()})
    if modified:
        source = output / name
        source.write_text(''.join(lines))
        result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', str(experiment / 'fpscr_adapter.h'),
                                 '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(base), '-c', str(source),
                                 '-o', str(output / (name + '.o'))], capture_output=True, text=True, timeout=180)
        (output / (name + '.build.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        directory = output
        print('Lowered and compiled', name, flush=True)
    records.append({'file': name, 'directory': str(directory), 'inputSha256': selected['sourceSha256'],
                    'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'objectSha256': hashlib.sha256((directory / (name + '.o')).read_bytes()).hexdigest(), 'modified': modified})
    paths.append(str(directory / (name + '.o')))
    text = ''.join(lines)
    functions = list(re.finditer(r'^void func_([0-9A-F]{8})\(', text, re.MULTILINE))
    for index, function in enumerate(functions):
        end = functions[index + 1].start() if index + 1 < len(functions) else len(text)
        body = text[function.start():end]
        markers = re.findall(r'UNIMPLEMENTED|//[^\n]*(?:stub|unhandled|approxim|ignored)', body)
        for _, word in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body):
            opcode = int(word, 16)
            if opcode >> 26 == 31 and ((opcode >> 1) & 1023) in (339, 467, 371):
                spr = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
                if spr not in {1, 8, 9, 26, 27, *range(272, 276), *range(912, 921), 1008}:
                    markers.append('UNVERIFIED_PROCESSOR_REGISTER_' + str(spr))
        if markers:
            quarantine.append((function.group(1), markers[0]))
policy = output / 'boot-quarantine.tsv'
policy.write_text(''.join(address + '\t' + re.sub(r'\s+', '_', marker) + '\n' for address, marker in quarantine))
report = {'result': 'PASS', 'changes': changes, 'records': records, 'baseObjectsSha256': hashlib.sha256((base / 'objects.json').read_bytes()).hexdigest(),
          'initialMsr': 0x30 if args.translated_fixture else 0,
          'cacheLoweringSha256': hashlib.sha256((cache / 'lowering.json').read_bytes()).hexdigest(),
          'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'adapterSha256': hashlib.sha256((experiment / 'fpscr_adapter.h').read_bytes()).hexdigest()}
(output / 'lowering.json').write_text(json.dumps(report, indent=2) + '\n')
exe = output / 'openshsm-mass-boot'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-DSHSM_PROCESSOR_ADAPTER', '-DSHSM_CACHE_ADAPTER',
                         *(['-DSHSM_BOOT_INITIAL_MSR=0x30'] if args.translated_fixture else []),
                         '-I', str(base), '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(upstream / 'nWiiAnalyzer/include'),
                         str(experiment / 'fpscr_boot.cpp'), str(experiment / 'processor_adapter.cpp'),
                         str(upstream / 'nWiiRuntime/src/core/loader.cpp'), *paths, '-o', str(exe)], capture_output=True, text=True, timeout=180)
(output / 'boot-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)], capture_output=True, text=True, timeout=30)
(output / 'boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout, (result.returncode, result.stdout[-3000:], result.stderr[-1000:])
report = {'result': 'BLOCKED_AT_ORIGINAL_BOOT', 'stdout': result.stdout, 'exitCode': result.returncode,
          'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(), 'policySha256': hashlib.sha256(policy.read_bytes()).hexdigest(),
          'wrapperSha256': hashlib.sha256((experiment / 'fpscr_boot.cpp').read_bytes()).hexdigest(),
          'baseWrapperSha256': hashlib.sha256((experiment / 'mass_boot.cpp').read_bytes()).hexdigest()}
(output / 'boot.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: automatic mtfsf lowering', len(changes), 'sites;', sum(record['modified'] for record in records), 'batches', flush=True)
print(result.stdout, flush=True)
