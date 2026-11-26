"""Replace one original dcbz stub with scoped existing-cache line zeroing."""
from pathlib import Path
import hashlib
import json
parent = Path('experiments/wii-static-recomp/build_reset_code_native.py')
body = parent.read_text().replace("base = private / 'mass-uart-ri-boot'", "base = private / 'mass-reset-code-boot'")
body = body.replace('reset-code-native', 'dc-zero-native').replace('verify_reset_code_dolphin.py', 'verify_dc_zero_dolphin.py')
start = body.index("before = ")
end = body.index("for row in build['records']:", start)
body = body[:start] + '''before = '    // 0x8021307C: 7C001FEC\\n    // dcbz (data cache block zero) - stub'
after = '    // 0x8021307C: 7C001FEC\\n    nwii::runtime::experiment_dcbz_line(ctx, ctx.gpr[3], 0x8021307c);'
''' + body[end:]
body = body.replace('reset_code_frontend.h', 'dc_zero_frontend.h').replace('reset_code_host.cpp', 'dc_zero_host.cpp')
body = body.replace('reset-host.cpp', 'dc-zero-host.cpp').replace('reset-code-probe', 'dc-zero-probe')
marker = "prefix = prefix[:prefix.index('int main(int argc, char** argv)')]"
body = body.replace(marker, marker + '''
prefix = prefix.replace('    if (context.inst_count > 100000)', '    if (context.pc == 0x807f0000) { throw std::runtime_error("DCZero flush return sentinel"); }\\n    if (context.inst_count > 100000)')''')
body = body.replace('RESET_CODE_NATIVE_REQUIRES_COMPARISON', 'DC_ZERO_NATIVE_REQUIRES_COMPARISON')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dc-zero-native/build.json')
report = json.loads(path.read_text())
report['parentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
path.write_text(json.dumps(report, indent=2) + '\n')
