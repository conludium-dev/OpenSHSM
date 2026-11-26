"""Link all generated objects and locate the first strict original-entrypoint boot blocker."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--processor', action='store_true')
parser.add_argument('--cache', action='store_true')
args = parser.parse_args()
args.processor |= args.cache
base = Path('work/private-game/static-recomp/mass-current')
output = Path('work/private-game/static-recomp/mass-processor') if args.processor else base
if args.cache:
    output = Path('work/private-game/static-recomp/mass-cache')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
objects = json.loads((base / 'objects.json').read_text())
assert objects['result'] == 'PASS' and objects['filesChecked'] == 125 and objects['failedFiles'] == 0
paths = []
quarantine = []
overrides = {}
if args.processor:
    lowering = json.loads((output / 'lowering.json').read_text())
    assert lowering['result'] == 'PASS'
    overrides = {record['file']: record for record in lowering['files']}
for record in objects['records']:
    selected = overrides.get(record['file'], record)
    directory = output if record['file'] in overrides else base
    path = directory / record['file']
    obj = directory / (record['file'] + '.o')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == selected['sourceSha256']
    assert hashlib.sha256(obj.read_bytes()).hexdigest() == selected['objectSha256']
    paths.append(str(obj))
    text = path.read_text()
    functions = list(re.finditer(r'^void func_([0-9A-F]{8})\(', text, re.MULTILINE))
    for index, function in enumerate(functions):
        end = functions[index + 1].start() if index + 1 < len(functions) else len(text)
        body = text[function.start():end]
        markers = re.findall(r'UNIMPLEMENTED|//[^\n]*(?:stub|unhandled|approxim|ignored)', body)
        for _, opcode_text in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', body):
            opcode = int(opcode_text, 16)
            if opcode >> 26 == 31 and ((opcode >> 1) & 1023) in (339, 467, 371):
                spr = ((opcode >> 16) & 31) | (((opcode >> 11) & 31) << 5)
                known_registers = {1, 8, 9, 26, 27, *range(272, 276), *range(912, 920)}
                if args.processor:
                    known_registers.add(920)
                if args.cache:
                    known_registers.add(1008)
                if spr not in known_registers:
                    markers.append('UNVERIFIED_PROCESSOR_REGISTER_' + str(spr))
        if markers:
            quarantine.append((function.group(1), markers[0]))
policy = output / 'boot-quarantine.tsv'
policy.write_text(''.join(address + '\t' + re.sub(r'\s+', '_', marker) + '\n' for address, marker in quarantine))
exe = output / 'openshsm-mass-boot'
extra = ['-DSHSM_PROCESSOR_ADAPTER', 'experiments/wii-static-recomp/processor_adapter.cpp'] if args.processor else []
if args.cache:
    extra.append('-DSHSM_CACHE_ADAPTER')
command = ['clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(base),
           '-I', str(upstream / 'nWiiRuntime/include'), '-I', str(upstream / 'nWiiAnalyzer/include'),
           'experiments/wii-static-recomp/mass_boot.cpp', str(upstream / 'nWiiRuntime/src/core/loader.cpp'),
           *extra, *paths, '-o', str(exe)]
print('Linking complete generated module with strict unavailable-service gates', flush=True)
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
(output / 'boot-link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-4000:]
result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                         capture_output=True, text=True, timeout=30)
(output / 'boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and 'BOOT_BOUNDARY' in result.stdout, (result.returncode, result.stdout[-3000:], result.stderr[-1000:])
report = {'result': 'BLOCKED_AT_ORIGINAL_BOOT', 'scope': 'Original DOL entrypoint began execution in fully linked native generated module; no game/menu acceptance.',
          'exitCode': result.returncode, 'stdout': result.stdout, 'quarantinedFunctions': len(quarantine),
          'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'wrapperSha256': hashlib.sha256(Path('experiments/wii-static-recomp/mass_boot.cpp').read_bytes()).hexdigest(),
          'objectReportSha256': hashlib.sha256((base / 'objects.json').read_bytes()).hexdigest(),
          'policySha256': hashlib.sha256(policy.read_bytes()).hexdigest(),
          'limits': ['Quarantine rejects functions containing emitter traps/stubs before execution; conservative path-level semantics remain unverified.',
                     'Unknown hardware/IOS/scheduler/interpreter services throw; no fabricated success, graphics/audio or original menu boot.',
                     'CPU bootstrap harness only; not replacement OpenSHSM renderer/runtime or a macOS game build.']}
(output / 'boot.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout, flush=True)
