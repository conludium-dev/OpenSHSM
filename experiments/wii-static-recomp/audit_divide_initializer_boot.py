"""Verify the whole function, exact source change and existing startup data contracts."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/audit_general_subtract_boot.py')
body = parent.read_text().replace('mass-general-subtract-boot', 'mass-divide-initializer-boot').replace(
    'mass-bias-alias-initializer-boot', 'mass-general-subtract-boot').replace('general_subtract', 'divide_initializer').replace(
    "('verify_divide_initializer_targeted.py','verify_divide_initializer_contract.py')", "('verify_divide_initializer_contract.py',)").replace(
    'general-subtract-boot-audit.json', 'divide-initializer-boot-audit.json').replace('output_26.cpp', 'output_37.cpp').replace(
    '0x800d8dfc', '0x8013b0c8').replace('0xec020028', '0xec010024').replace(
    'address=800d8dfc opcode=ec020028', 'address=8013b0c8 opcode=ec010024').replace(
    'SHSM_GENERAL_SUBTRACT_DISABLED', 'SHSM_DIVIDE_INITIALIZER_DISABLED').replace(
    'pc=800d8dc4 lr=8021e8f4', 'pc=8013b0c0 lr=8021e8f4')
line = "assert (output / 'boot-wrapper.cpp').read_bytes() == (base / 'boot-wrapper.cpp').read_bytes()"
replacement = '''wrapper = (base / 'boot-wrapper.cpp').read_text().replace('int main(int argc, char** argv) {',
    '#include "divide_initializer_probe.h"' + chr(10) + 'int main(int argc, char** argv) {' + chr(10) + '    if (argc == 2 && std::string(argv[1]) == "--divide-initializer-probe") { return experiment_divide_initializer_probe(); }')
assert (output / 'boot-wrapper.cpp').read_text() == wrapper
'''
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
header_check = "assert (output / 'divide_initializer_adapter.h').read_bytes() == (experiment / 'divide_initializer_adapter.h').read_bytes()"
header_replacement = "assert (output / 'divide_initializer_adapter.h').read_bytes() == (root / 'divide-initializer-component/divide_initializer_adapter.h').read_bytes()"
body = body.replace(marker, f'body = body.replace({line!r}, {replacement!r}).replace({header_check!r}, {header_replacement!r})\n' + marker)
body = body.replace('ORIGINAL_GENERAL_SUBTRACT5120_RUNS_NATIVE_BOOT_CONTINUED', 'ORIGINAL_WHOLE_DIVIDE5_NATIVE128_BOOT_CONTINUED').replace(
    'One exact subtraction body changed;124 objects retained, no wrapper/backend change.', 'One exact division body changed;124 objects retained, wrapper adds isolated whole-function probe only.').replace(
    'Raw1024 and expanded4096 original runs/result/paired-lanes/FPSCR/preserved operand;12 refusals andUBSan5120.', 'Whole original5 instructions128/global store-neighbor/FPR lanes/FPSCR/native-return and12 atomic refusals match.').replace(
    'PASS general-subtract5120/one-object delta', 'PASS whole-divide5/native128/one-object delta')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
