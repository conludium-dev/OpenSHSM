"""Reproduce dispatch for the new opcode without changing pinned arithmetic core files."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/multiply-register-component')
output.mkdir(exist_ok=True)
source = (experiment / 'single_arithmetic_adapter.h').read_text()
start = source.index('inline void experiment_single_arithmetic(')
function = source[start:source.rfind('\n}')].replace('experiment_single_arithmetic','experiment_multiply_register')
old = '(opcode != 0xec220824 && opcode != 0xec000072)'
assert function.count(old) == 1
function = function.replace(old,'opcode != 0xec010032')
header = '#pragma once\n#include "single_arithmetic_adapter.h"\n\nnamespace nwii::runtime {\n' + function + '\n}\n'
(output / 'multiply_register_adapter.h').write_text(header)
(output / 'single_arithmetic_adapter.h').write_text(source)
probe = (experiment / 'single_arithmetic_probe.cpp').read_text().replace('single_arithmetic_adapter.h','multiply_register_adapter.h').replace(
    'divide ? 2 : 0','divide ? 2 : 1').replace('context.fpr[1] = std::bit_cast<double>(b);','context.fpr[divide ? 1 : 0] = std::bit_cast<double>(b);').replace(
    'experiment_single_arithmetic(context, opcode);','if (divide) { experiment_single_arithmetic(context, opcode); } else { experiment_multiply_register(context, opcode); }')
(output / 'multiply-register-probe.cpp').write_text(probe)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'preparation.json').write_text(json.dumps({'preparerSha256':sha(Path(__file__)),
    'parentHelperSha256':sha(experiment / 'single_arithmetic_adapter.h'),
    'headerSha256':sha(output / 'multiply_register_adapter.h'),'probeSha256':sha(output / 'multiply-register-probe.cpp'),
    'limits':['Only dispatch opcode whitelist expanded in a separate entry point; exact existing integer arithmetic core retained.',
        'No guest register remapping or temporary CPU context; actual decoded FA/FC used. Original/native comparison required.']},indent=2) + '\n')
