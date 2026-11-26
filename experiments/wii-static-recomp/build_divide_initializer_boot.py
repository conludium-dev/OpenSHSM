"""Bind the measured division routing and whole-function probe in the existing module."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_general_subtract_boot.py')
body = parent.read_text().replace('mass-general-subtract-boot', 'mass-divide-initializer-boot').replace(
    'mass-bias-alias-initializer-boot', 'mass-general-subtract-boot').replace('general_subtract', 'divide_initializer').replace(
    'output_26.cpp', 'output_37.cpp').replace('SHSM_GENERAL_SUBTRACT_DISABLED', 'SHSM_DIVIDE_INITIALIZER_DISABLED')
body = body.replace("('audit_bias_alias_initializer_boot.py','verify_divide_initializer_native.py','verify_divide_initializer_targeted.py','verify_divide_initializer_contract.py')",
    "('audit_general_subtract_boot.py','verify_divide_initializer_capture.py')")
line = "(output / 'divide_initializer_adapter.h').write_bytes((experiment / 'divide_initializer_adapter.h').read_bytes())"
assert body.count(line) == 1
body = body.replace(line, '''component = root / 'divide-initializer-component'
prep = json.loads((component / 'preparation.json').read_text())
assert prep['parentHelperSha256'] == sha(output / 'single_arithmetic_adapter.h')
assert prep['headerSha256'] == sha(component / 'divide_initializer_adapter.h')
assert prep['probeSha256'] == sha(component / 'divide_initializer_probe.h')
for name in ('divide_initializer_adapter.h','divide_initializer_probe.h'):
    (output / name).write_bytes((component / name).read_bytes())
replace(wrapper, 'int main(int argc, char** argv) {', '#include "divide_initializer_probe.h"' + chr(10) + 'int main(int argc, char** argv) {' + chr(10) + '    if (argc == 2 && std::string(argv[1]) == "--divide-initializer-probe") { return experiment_divide_initializer_probe(); }')
''')
body = body.replace('Exact general-subtraction body changed', 'Exact division-routing body changed')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
