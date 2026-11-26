"""Enable only the original measured cold-reset read in the current boot."""
from pathlib import Path
import hashlib
import json
parent = Path('experiments/wii-static-recomp/build_uart_ri_boot.py')
body = parent.read_text().replace("base = private / 'mass-memory-protection-boot'", "base = private / 'mass-uart-ri-boot'")
body = body.replace("output = private / 'mass-uart-ri-boot'", "output = private / 'mass-reset-code-boot'")
body = body.replace('verify_uart_ri_native.py', 'verify_reset_code_native.py').replace('uart-ri-native', 'reset-code-native')
body = body.replace('experimentExiRiUart = !std::getenv', 'experimentResetCode = !std::getenv')
body = body.replace('SHSM_RI_UART_DISABLED', 'SHSM_RESET_DISABLED')
body = body.replace("'SHSM_RESET_DISABLED')", "'SHSM_RI_UART_DISABLED', 'SHSM_RESET_DISABLED')")
body = body.replace('memory_protection_frontend.h', 'reset_code_frontend.h')
line = "wrapper.write_bytes((base / 'boot-wrapper.cpp').read_bytes())"
assert body.count(line) == 1
body = body.replace(line, '''wrapper_body = (base / 'boot-wrapper.cpp').read_text()
marker = '    const int result = original_boot_main(3, argv);'
assert wrapper_body.count(marker) == 1
wrapper_body = wrapper_body.replace(marker, marker + '\\n    std::cout << "BOOT_RESET reads=" << nwii::runtime::experimentResetCodeReads << "\\\\n";')
wrapper.write_text(wrapper_body)''')
body = body.replace("'BOOT_FLUSH ')", "'BOOT_FLUSH ', 'BOOT_RESET ')")
body = body.replace('UART_RI_BOOT_REQUIRES_AUDIT', 'RESET_CODE_BOOT_REQUIRES_AUDIT')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-reset-code-boot/boot.json')
report = json.loads(path.read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Cold read uses existing vendor PI0value verified against original fixture; warm parameter branch unchanged.',
    'Reset writes/buttons/events and non-cold PI state remain unsupported; no original first frame/menu/full-game proof.']
path.write_text(json.dumps(report, indent=2) + '\n')
