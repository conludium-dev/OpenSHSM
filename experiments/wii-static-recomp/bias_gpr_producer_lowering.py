"""Preserve FP facts while invalidating only the destination of known GPR-only producers."""
from pathlib import Path
from bias_constructor_lowering import lower as lower_prefix
from bias_register_variant_lowering import lower as lower_register

parent = Path(__file__).with_name('bias_block_lowering.py')
body = parent.read_text()
marker = "exec(compile(body,str(parent),'exec'),namespace)"
assert body.count(marker) == 1
injection = '''body = body.replace("'fsubs f0, f0, f1' not in text", "'fsubs ' not in text")
body = body.replace('if word == 0xec000828:', 'if primary == 59 and ((word >> 1) & 31) == 20 and not (word & 0x7c1):')
body = body.replace('floats.get(0) == expected and floats.get(1)', 'floats.get(base) == expected and floats.get((word >> 11) & 31)')
body = body.replace('            elif word == 0x7c0802a6:', '            elif primary == 31 and ((word >> 1) & 1023) == 75:' + chr(10) + '                registers[target] = None' + chr(10) + '            elif primary == 21:' + chr(10) + '                registers[base] = None' + chr(10) + '            elif word == 0x7c0802a6:')
'''
body = body.replace(marker, injection + marker)
namespace = {'__file__': __file__}
exec(compile(body, str(parent), 'exec'), namespace)


def select(dol, directory):
    return [site for site in namespace['select'](dol, directory)
        if site['opcode'] in (0xec000828, 0xec401828, 0xec421828, 0xec211828, 0xec201028)]


def lower(text, dol, sites):
    text, first = lower_prefix(text, dol, sites)
    text, second = lower_register(text, dol, sites)
    changes = first + second
    for change in changes:
        after = change['after'].replace('SHSM_BIAS_CONSTRUCTORS_DISABLED', 'SHSM_BIAS_GPR_PRODUCERS_DISABLED').replace(
            'SHSM_BIAS_VARIANTS_DISABLED', 'SHSM_BIAS_GPR_PRODUCERS_DISABLED')
        text = text.replace(change['after'], after)
        change['after'] = after
    return text, changes
