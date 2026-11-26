"""Reuse the unchanged arithmetic function and prepare a whole-function native caller."""
from pathlib import Path
import json
import hashlib

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/divide-initializer-component')
output.mkdir(exist_ok=True)
source = (experiment / 'single_arithmetic_adapter.h').read_text()
start = source.index('inline void experiment_single_arithmetic(')
function = source[start:source.rfind('\n}')].replace('experiment_single_arithmetic', 'experiment_divide_initializer')
old = '(opcode != 0xec220824 && opcode != 0xec000072)'
assert function.count(old) == 1 and function.count('const bool divide = opcode == 0xec220824;') == 1
function = function.replace(old, 'opcode != 0xec010024').replace('const bool divide = opcode == 0xec220824;', 'const bool divide = opcode == 0xec010024;')
(output / 'divide_initializer_adapter.h').write_text('#pragma once\n#include "single_arithmetic_adapter.h"\n\nnamespace nwii::runtime {\n' + function + '\n}\n')
probe = (experiment / 'fp_initializer_probe.h').read_text().replace('func_8000C2F4', 'func_8013B0C0').replace(
    'experiment_fp_initializer_probe', 'experiment_divide_initializer_probe').replace('0x8000c2f4', '0x8013b0c0').replace(
    '0x8052861c', '0x80527ec0').replace('0x80529158', '0x80529f38').replace('0x8052915c', '0x80529f3c').replace(
    'FP_INITIALIZER_PROBE', 'DIVIDE_INITIALIZER_PROBE')
(output / 'divide_initializer_probe.h').write_text(probe)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'preparation.json').write_text(json.dumps({'preparerSha256': sha(Path(__file__)),
    'parentHelperSha256': sha(experiment / 'single_arithmetic_adapter.h'),
    'parentProbeSha256': sha(experiment / 'fp_initializer_probe.h'),
    'headerSha256': sha(output / 'divide_initializer_adapter.h'), 'probeSha256': sha(output / 'divide_initializer_probe.h'),
    'limits': ['Only name, opcode admission and divide-dispatch predicate changed; arithmetic algorithm shared unchanged.',
        'Native caller executes actual recompiled five-instruction body, checks SP/LR/MSR return contract.']}, indent=2) + '\n')
