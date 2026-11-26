"""Enable verified DCZeroRange, leaving other dcbz stubs quarantined."""
from pathlib import Path
import hashlib
import json
parent = Path('experiments/wii-static-recomp/build_uart_ri_boot.py')
body = parent.read_text().replace("base = private / 'mass-memory-protection-boot'", "base = private / 'mass-reset-code-boot'")
body = body.replace("output = private / 'mass-uart-ri-boot'", "output = private / 'mass-dc-zero-boot'")
body = body.replace('verify_uart_ri_native.py', 'verify_dc_zero_native.py').replace('uart-ri-native', 'dc-zero-native')
body = body.replace('experimentExiRiUart = !std::getenv', 'experimentDcZero = !std::getenv')
body = body.replace('SHSM_RI_UART_DISABLED', 'SHSM_DC_ZERO_DISABLED')
body = body.replace("'SHSM_DC_ZERO_DISABLED')", "'SHSM_RI_UART_DISABLED', 'SHSM_RESET_DISABLED', 'SHSM_DC_ZERO_DISABLED')")
body = body.replace('memory_protection_frontend.h', 'dc_zero_frontend.h')
line = "wrapper.write_bytes((base / 'boot-wrapper.cpp').read_bytes())"
assert body.count(line) == 1
body = body.replace(line, '''wrapper_body = (base / 'boot-wrapper.cpp').read_text()
marker = '    const int result = original_boot_main(3, argv);'
assert wrapper_body.count(marker) == 1
wrapper_body = wrapper_body.replace(marker, marker + '\\n    std::cout << "BOOT_DCZERO lines=" << nwii::runtime::experimentDcZeroLines << "\\\\n";')
wrapper.write_text(wrapper_body)
policy = output / 'boot-quarantine.tsv'
removed = '80213060\\t//_dcbz_(data_cache_block_zero)_-_stub\\n'
policy_text = policy.read_text()
assert policy_text.count(removed) == 1
policy.write_text(policy_text.replace(removed, ''))''')
body = body.replace("'BOOT_FLUSH ')", "'BOOT_FLUSH ', 'BOOT_DCZERO ')")
body = body.replace('UART_RI_BOOT_REQUIRES_AUDIT', 'DC_ZERO_BOOT_REQUIRES_AUDIT')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-dc-zero-boot/boot.json')
report = json.loads(path.read_text())
report['parentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['removedPolicy'] = '80213060\t//_dcbz_(data_cache_block_zero)_-_stub\n'
report['limits'] = ['Only verified original DCZeroRange stub replaced; other dcbz/dcbz_l procedures remain guarded.',
    'Cached line zeroing uses existing cache/BAT model, no physical bus/replacement timing/full-game acceptance.']
path.write_text(json.dumps(report, indent=2) + '\n')
