"""Reuse actual DEC/callback/SDK/SC/frame gates with the existing VI observer enabled."""
from pathlib import Path
import hashlib
import json
import os

base = Path('experiments/wii-static-recomp/verify_stock_dec_ee_gate.py')
script = base.read_text()
start = script.index("before, after = build['patch']")
end = script.index("base = Path('experiments", start)
script = script[:start] + '''before, after = build['patch']
source = Path(build['sourcePath']).read_text()
assert source.count(after) == 1
assert source.removeprefix('#include "stock_vi_timer_profile.h"\\n').replace(after, before, 1) == Path(build['originalSourcePath']).read_text()
assert build['arguments'] == json.loads((root / 'window-ios-o2/build.json').read_text())['arguments']
''' + script[end:]
script = script.replace("window-dec-ee-gate", "window-vi-timer-profile")
script = script.replace("window-dispatch-o2/build.json", "window-current-vi-timer/build.json")
script = script.replace("Path(build['sourcePath']).read_text().replace(build['patch'][1], build['patch'][0], 1)",
    "Path(build['sourcePath']).read_text().removeprefix('#include \\\"stock_vi_timer_profile.h\\\"\\\\n').replace(build['patch'][1], build['patch'][0], 1)")
script = script.replace('DEC_EE_GATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL',
    'VI_TIMER_PROFILE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL')
script = script.replace("exec(compile(script, str(base), 'exec'), {'__file__': __file__})",
    "script = script.replace(\"flags = json.loads\", \"env['NWII_VI_TIMER_PROFILE'] = '1'\\nflags = json.loads\", 1)\nexec(compile(script, str(base), 'exec'), {'__file__': __file__})")
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = Path('work/private-game/static-recomp/stock-baseline/window-vi-timer-profile/component-verification.json')
report = json.loads(report_path.read_text())
report['observerEnabled'] = True
report['wrapperVerifierSha256'] = hashlib.sha256(base.read_bytes()).hexdigest()
report['limits'] = [
    'Only existing IOS recurring callback receives opt-in counters; source restoration and all other archive members exact.',
    'Observer enabled during actual scheduler/callback4/DEC9/SDK7/emittedSC3 and18late full YUV/raw selected PPC endpoint fixtures.',
    '32 native truth-table cases separately preserve original VI acceptance/MMU read counts.',
    'Fixtures do not prove physical Wii/asynchronous pending IRQ cadence, live timing neutrality or performance.',
    'Synchronous diagnostic stderr can perturb an observed run; no default promotion or FPS correction.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
