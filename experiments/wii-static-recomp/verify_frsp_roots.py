"""Check isolated root generation against DOL/dtk and compile without activating it."""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess
from frsp_lowering import lower

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'frsp-roots'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
assert generation['scriptSha256'] == sha(experiment / 'build_frsp_roots.py')
assert generation['baseDriverSha256'] == sha(experiment / 'nwii_mass_driver.cpp')
assert generation['driverSha256'] == sha(output / 'root-driver.cpp')
assert generation['analyzerSha256'] == sha(private / 'phone-services/analyzer-profile.cpp')
assert generation['profileSha256'] == sha(private / 'phone-services/analyzer-profile.tsv')
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert generation['originalSha256'] == sha(original_path)
original = original_path.read_bytes()
header = struct.unpack('>64I', original[:256])
roots = [(0x801015cc, 0x801016a4, 'auto_03_80100D70_text.s'),
         (0x801123dc, 0x801125a8, 'auto_03_8010EE1C_text.s'),
         (0x803d1470, 0x803d1a1c, 'auto_03_803CBFD4_text.s')]
catalogue = [[int(value, 16) for value in row.split('\t')[:3]] for row in generation['functions']]
assert catalogue == [[entry, entry, end] for entry, end, _ in roots]
source = output / 'output_0.cpp'
assert sha(source) == generation['generatedSha256']['output_0.cpp']
text = source.read_text()
records = [(int(address, 16), int(opcode, 16)) for address, opcode in re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', text)]
assert len(records) == 532 and len({address for address, _ in records}) == 532
dtk_proofs = []
for entry, end, filename in roots:
    asm = private / 'dtk-output/asm' / filename
    assembly = asm.read_text()
    assert re.search(rf'# \.text:0x[0-9A-F]+ \| 0x{entry:08X} \| size: 0x{end-entry:X}\n\.fn fn_{entry:08X}, global', assembly)
    dtk_instructions = {int(address, 16): int(opcode.replace(' ', ''), 16) for address, opcode in
                        re.findall(r'/\* ([0-9A-F]{8}) [0-9A-F]{8}  ([0-9A-F ]{11}) \*/', assembly)}
    selected = [(address, opcode) for address, opcode in records if entry <= address < end]
    assert len(selected) == (end - entry) // 4
    for address, opcode in selected:
        section = next(index for index in range(7) if header[18 + index] <= address < header[18 + index] + header[36 + index])
        assert struct.unpack_from('>I', original, header[section] + address - header[18 + section])[0] == opcode
        assert dtk_instructions[address] == opcode
    dtk_proofs.append({'entry': hex(entry), 'end': hex(end), 'instructions': len(selected), 'asmSha256': sha(asm)})
modified, changes = lower(text, original)
missing = set(json.loads((private / 'mass-frsp/audit.json').read_text())['untranslatedAddresses'])
assert len(changes) == 7 and {change['address'] for change in changes} == missing
target = output / 'lowered-roots.cpp'
target.write_text(modified)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
obj = output / 'lowered-roots.o'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', str(experiment / 'frsp_adapter.h'),
                         '-include', str(private / 'mass-current/functions.h'), '-I', str(upstream / 'nWiiRuntime/include'),
                         '-I', str(output), '-c', str(target), '-o', str(obj)], capture_output=True, text=True, timeout=60)
(output / 'native-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
report = {'result': 'THREE_MISSING_ROOTS_DOL_DTK_MATCH_NATIVE_OBJECT_COMPILED_NOT_INTEGRATED',
          'instructions': 532, 'frspSites': 7, 'dtkProofs': dtk_proofs,
          'generationSha256': sha(output / 'generation.json'), 'objectSha256': sha(obj),
          'sourceSha256': sha(target), 'changes': changes, 'verifierSha256': sha(Path(__file__)),
          'limits': ['Dtk independent boundaries/opcodes agree; generated C++ semantics of enclosing functions not verified.',
                     'Object compilation only, not full-module dispatch/link or original-function execution.',
                     'New roots require existing memory/control/FP lowering before runtime integration; no NI activation.']}
(output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS three roots/532instructions match DOL/dtk; seven FRSP sites translated; native object compiled, runtime integration pending')
