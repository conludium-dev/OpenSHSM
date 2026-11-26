"""Bind PC input only at recovered entry PCs in a private generated source copy."""


def adapt(text, name):
    entries = {
        'output_1.cpp': {
            '80009DD0': 'openshsm::experiment::bootstrap_pc_primary_input(ctx);',
        },
        'output_44.cpp': {
            '8027AAC0': 'openshsm::experiment::forward_pc_kpad_read(ctx, false); return;',
            '8027AAD0': 'openshsm::experiment::forward_pc_kpad_read(ctx, true); return;',
            '80280AC0': 'openshsm::experiment::forward_pc_wpad_probe(ctx); return;',
        },
    }[name]
    text = '#include "stock_input_sdk_bridge.h"\n' + text
    for address, statement in entries.items():
        marker = f'loc_{address}: ;\n'
        assert text.count(marker) == 1, address
        text = text.replace(marker, marker + '    ' + statement + '\n', 1)
    return text
