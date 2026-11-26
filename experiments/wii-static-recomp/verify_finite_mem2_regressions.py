"""Re-link existing positive oracles and finite accounting guards against current boot objects."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_uart_ri_regressions.py')
body = parent.read_text().replace("base = private / 'uart-ri-native'", "base = private / 'mass-finite-mem2-boot'")
body = body.replace('uart-ri-regressions', 'finite-mem2-regressions').replace("base / 'build.json'", "base / 'boot.json'")
body = body.replace("for name in ('loader-bat-seed.h', 'mass_boot.cpp', 'memory-protection-bat-plan.h'):",
    "for name in ('loader-bat-seed.h', 'mass_boot.cpp', 'memory-protection-bat-plan.h', 'memory_protection_frontend.h', 'dc_zero_frontend.h', 'reset_code_frontend.h', 'finite_mem2_clear.h'):")
body = body.replace("for name in ('uart', 'getid', 'memory'):", "for name in ('uart', 'getid', 'memory', 'dczero', 'finite'):")
marker = '    chosen_prefix = prefix'
body = body.replace(marker, '''    if name == 'memory':
        body = (private / 'memory936-native/memory936_host.cpp').read_text()
    if name == 'dczero':
        body = (experiment / 'dc_zero_host.cpp').read_text()
    if name == 'finite':
        body = (experiment / 'finite_mem2_guards.cpp').read_text()
''' + marker, 1)
body = body.replace("    host.write_text(", '''    if name == 'dczero':
        chosen_prefix = prefix.replace('    if (context.inst_count > 100000)', '    if (context.pc == 0x807f0000) { throw std::runtime_error("DCZero flush return sentinel"); }\\n    if (context.inst_count > 100000)')
    host.write_text(''' )
body = body.replace('#include "memory_protection_frontend.h"', '#include "finite_mem2_clear.h"')
body = body.replace("str(experiment / 'memory_protection_frontend.h')", "str(output / 'finite_mem2_clear.h')")
marker = '    reference = private / '
start = body.index(marker)
end = body.index("(output / 'verification.json')", start)
body = body[:start] + '''    if name == 'finite':
        assert result.stdout == 'FINITE_MEM2_GUARDS 16 COUNT 1765312 DISABLED_ORIGINAL_POLL\\n'
        reports[name] = {'logSha256': sha(output / (name + '.log')), 'executableSha256': sha(exe)}
    else:
        reference = private / {'uart': 'uart-native/native.log', 'getid': 'exi-getid-native/native.log',
            'memory': 'memory936-native/native.log', 'dczero': 'dc-zero-native/normal.log'}[name]
        assert result.stdout == reference.read_text(), name
        reports[name] = {'executableSha256': sha(exe), 'logSha256': sha(output / (name + '.log')), 'referenceSha256': sha(reference)}
''' + body[end:]
body = body.replace('RI_OPT_IN_DISABLED_UART16_GETID16_MEMORY16_REGRESSION_PASS', 'CURRENT_BOOT_UART16_GETID16_MEMORY93616_DCZERO32_FINITE16_PASS')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/finite-mem2-regressions/verification.json')
report = json.loads(path.read_text())
report['parentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Current-object original-verified positive regressions plus finite accounting contract negatives.',
    'Synthetic guard traversal is not original execution; full boot proves the actual finite function return separately.']
path.write_text(json.dumps(report, indent=2) + '\n')
