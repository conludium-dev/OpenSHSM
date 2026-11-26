"""Bind the measured aliasing bias operation and existing scalar arithmetic in one source prefix."""
from pathlib import Path
import re
from bias_block_register_lowering import namespace
from bias_register_variant_lowering import lower as lower_register


def select(dol, directory):
    return [site for site in namespace['select'](dol, directory)
        if site['function'] == 0x800d8dc4 and site['address'] == 0x800d8df0 and site['opcode'] == 0xec211828]


def lower(text, dol, sites):
    text, changes = lower_register(text, dol, sites)
    if not changes:
        return text, changes
    assert len(changes) == 1
    for change in changes:
        after = change['after'].replace('SHSM_BIAS_VARIANTS_DISABLED', 'SHSM_BIAS_ALIAS_INITIALIZER_DISABLED')
        text = text.replace(change['after'], after)
        change['after'] = after
    for address, opcode, mnemonic in ((0x800d8df4, 0xec220824, 'fdivs'), (0x800d8df8, 0xec000072, 'fmuls')):
        pattern = re.compile(r'(    // 0x' + f'{address:08X}: {opcode:08X}' + r'\n)(.*?)(?=    \+\+ctx\.inst_count;\nloc_)', re.S)
        assert len(pattern.findall(text)) == 1
        match = pattern.search(text)
        assert 'experiment_ni_guard' in match[2] and mnemonic in match[2]
        after = (f'    if (std::getenv("SHSM_BIAS_ALIAS_INITIALIZER_DISABLED")) {{ nwii::runtime::experiment_ni_guard(ctx, 0x{opcode:08x}, 0x{address:08x}); }}\n'
            f'    nwii::runtime::experiment_single_arithmetic(ctx, 0x{opcode:08x});\n')
        text = pattern.sub(lambda item: item[1] + after, text)
        changes.append({'address': address, 'opcode': opcode, 'before': match[2], 'after': after})
    return '#include "single_arithmetic_adapter.h"\n' + text, changes
