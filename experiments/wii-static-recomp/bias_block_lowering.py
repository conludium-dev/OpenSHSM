"""Reuse the original symbolic rule with conservative resets at control-flow boundaries."""
from pathlib import Path
import ast
import re
import struct
import hashlib
from bias_constructor_lowering import lower as lower_prefix

parent = Path(__file__).with_name('bias_constructor_lowering.py')
node = next(node for node in ast.parse(parent.read_text()).body if isinstance(node,ast.FunctionDef) and node.name == 'select')
body = ast.get_source_segment(parent.read_text(),node)
body = body.replace('        floats, stack = {}, {}','        floats, stack = {}, {}\n        active = True\n        block_start = int(rows[0][0],16)\n        boundary = "function-entry"')
marker = '            if word == 0xec000828:'
assert body.count(marker) == 1
body = body.replace(marker,'''            if primary in (16,18) or (primary == 19 and ((word >> 1) & 1023) in (16,528)):
                registers = {1: ('stack',0),2:0x805335e0,13:0x8052e720}
                floats,stack = {},{}
                block_start = int(address,16) + 4
                boundary = 'after-call' if word & 1 else 'after-branch'
                active = word != 0x4e800020
                continue
            if not active:
                continue
''' + marker)
body = body.replace("'opcode': word, 'assemblySha256':", "'opcode': word, 'blockStart':block_start,'boundary':boundary,'assemblySha256':")
body = body.replace('                break\n            origin', '                active = False\n                continue\n            origin')
body = body.replace('primary in (32, 36, 37, 50)', 'primary in (32, 36, 37, 48, 50)')
body = body.replace('                elif isinstance(location, int):','                elif primary == 48:\n                    floats[target] = None\n                elif isinstance(location, int):')
body = body.replace('                    break','                    active = False\n                    continue').replace(
    '                break','                active = False\n                continue')
namespace = {'Path':Path,'re':re,'struct':struct,'hashlib':hashlib}
exec(compile(body,str(parent),'exec'),namespace)
select = namespace['select']


def lower(text,dol,sites):
    text,changes = lower_prefix(text,dol,sites)
    for change in changes:
        updated = change['after'].replace('SHSM_BIAS_CONSTRUCTORS_DISABLED','SHSM_BIAS_BLOCKS_DISABLED')
        text = text.replace(change['after'],updated)
        change['after'] = updated
    return text,changes
