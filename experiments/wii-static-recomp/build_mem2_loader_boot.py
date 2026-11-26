"""Apply measured direct-DOL emulator loader fields, retaining original arena initialization."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
proof_path = private / 'dolphin-loader-snapshot/comparison.json'
import subprocess
subprocess.run(['python3', str(experiment / 'verify_loader_snapshot_dolphin.py')], check=True)
proof = json.loads(proof_path.read_text())
fields = proof['fields']
addresses = (0x3100, 0x3104, 0x3118, 0x311c, 0x3120, 0x3124, 0x3128, 0x3130, 0x3134)
seeds = ', '.join('{0x%04x, 0x%s}' % (address, fields[f'{address:08x}']) for address in addresses)
parent = experiment / 'build_uart_ri_boot.py'
body = parent.read_text().replace("base = private / 'mass-memory-protection-boot'", "base = private / 'mass-dc-zero-boot'")
body = body.replace("output = private / 'mass-uart-ri-boot'", "output = private / 'mass-mem2-loader-boot'")
body = body.replace('verify_uart_ri_native.py', 'verify_dc_zero_native.py').replace('uart-ri-native', 'dc-zero-native')
old = "entry = entry.replace(marker, marker + '\\n    nwii::runtime::experimentExiRiUart = !std::getenv(\"SHSM_RI_UART_DISABLED\");')"
assert body.count(old) == 1
body = body.replace(old, '''old_seed = 'std::array<std::array<uint32_t, 2>, 4>{{\\n            {0x3100, 0x01800000}, {0x3104, 0x01800000}, {0x311c, 0x04000000}, {0x3120, 0x93400000}}}'
assert entry.count(old_seed) == 1
new_seed = 'std::array<std::array<uint32_t, 2>, 9>{{' + seeds + '}}'
entry = entry.replace(old_seed, new_seed)
entry = entry.replace('if (!std::getenv("SHSM_MI_NO_SIZE_FIXTURE")) {', 'if (!std::getenv("SHSM_MI_NO_SIZE_FIXTURE") && !std::getenv("SHSM_MEM2_LOADER_DISABLED")) {')
''')
body = body.replace('memory_protection_frontend.h', 'dc_zero_frontend.h')
body = body.replace("'SHSM_RI_UART_DISABLED')", "'SHSM_RI_UART_DISABLED', 'SHSM_RESET_DISABLED', 'SHSM_DC_ZERO_DISABLED', 'SHSM_MEM2_LOADER_DISABLED')")
body = body.replace("environment['SHSM_RI_UART_DISABLED'] = '1'", "environment['SHSM_MEM2_LOADER_DISABLED'] = '1'")
body = body.replace('UART_RI_BOOT_REQUIRES_AUDIT', 'MEM2_LOADER_BOOT_REQUIRES_AUDIT')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__, 'seeds': seeds})
path = private / 'mass-mem2-loader-boot/boot.json'
report = json.loads(path.read_text())
report['loaderProofSha256'] = hashlib.sha256(proof_path.read_bytes()).hexdigest()
report['loaderFields'] = {f'{address:08x}': fields[f'{address:08x}'] for address in addresses}
report['limits'] = ['Measured emulator direct-DOL startup profile, not retail apploader or physical Wii.',
    'Only loader fields change; original OSInit/arena setters/clearing and all hardware guards retained.',
    'Disabled loader control omits size fields too; it should refuse before BAT initialization.']
path.write_text(json.dumps(report, indent=2) + '\n')
