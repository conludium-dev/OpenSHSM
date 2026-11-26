"""Extend the existing conservative symbolic selector to FPR register variants."""
from pathlib import Path
import ast
import re

parent = Path(__file__).with_name('bias_constructor_lowering.py')
node = next(node for node in ast.parse(parent.read_text()).body if isinstance(node,ast.FunctionDef) and node.name == 'select')
body = ast.get_source_segment(parent.read_text(),node)
body = body.replace("'fsubs f0, f0, f1' not in text", "'fsubs ' not in text")
body = body.replace('if word == 0xec000828:', 'if primary == 59 and ((word >> 1) & 31) == 20 and not (word & 0x7c1):')
body = body.replace('floats.get(0) == expected and floats.get(1)', 'floats.get(base) == expected and floats.get((word >> 11) & 31)')
body = body.replace('primary in (32, 36, 37, 50)', 'primary in (32, 36, 37, 48, 50)')
body = body.replace('                elif isinstance(location, int):', '                elif primary == 48:\n                    floats[target] = None\n                elif isinstance(location, int):')
namespace = {'Path':Path,'re':re,'struct':__import__('struct'),'hashlib':__import__('hashlib')}
exec(compile(body,str(parent),'exec'),namespace)
select = namespace['select']


def lower(text,dol,sites):
    changes = []
    for site in sites:
        address,opcode = site['address'],site['opcode']
        if opcode == 0xec000828:
            continue
        destination,left,right = (opcode >> 21) & 31,(opcode >> 16) & 31,(opcode >> 11) & 31
        before = (f'    nwii::runtime::experiment_ni_guard(ctx, 0x{opcode:08x}, 0x{address:08x});\n'
            f'    ctx.fpr[{destination}] = (float)(ctx.fpr[{left}] - ctx.fpr[{right}]); // fsubs')
        if before not in text:
            continue
        assert text.count(before) == 1
        after = (f'    if (std::getenv("SHSM_BIAS_VARIANTS_DISABLED")) {{ nwii::runtime::experiment_ni_guard(ctx, 0x{opcode:08x}, 0x{address:08x}); }}\n'
            f'    nwii::runtime::experiment_fsubs_integer_bias(ctx, 0x{opcode:08x});')
        text = text.replace(before,after)
        changes.append({**site,'before':before,'after':after})
    return text,changes
