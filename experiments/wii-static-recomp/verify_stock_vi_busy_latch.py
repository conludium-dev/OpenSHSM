"""Verify IOS-only source/member change and existing actual native regression gates."""
from pathlib import Path
import hashlib
import json

base = Path('experiments/wii-static-recomp/verify_stock_dec_ee_gate.py')
script = base.read_text()
script = script.replace("output = root / 'window-dec-ee-gate'", "output = root / 'window-vi-busy-latch'")
script = script.replace('"output = root / \'window-dec-ee-gate\'"', '"output = root / \'window-vi-busy-latch\'"')
script = script.replace('window-dispatch-o2/build.json', 'window-current-vi-timer/build.json')
script = script.replace("assert source.index('EventScheduler::get().advance(ctx, ctx.read_timebase());') < source.index(after)",
    "assert 'if (use_new_path && (handler_in_flight || (!idle && sched_disabled))) {' in source")
script = script.replace('DEC_EE_GATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL', 'VI_BUSY_LATCH_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL')
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = Path('work/private-game/static-recomp/stock-baseline/window-vi-busy-latch/component-verification.json')
report = json.loads(report_path.read_text())
report['baseWrapperSha256'] = hashlib.sha256(base.read_bytes()).hexdigest()
report['limits'] = [
    'Single existing recurring VI busy-gate removal; exact source restoration, allother archive members/objects unchanged.',
    'Actual scheduler/callback4/DEC9/SDK7/SC3 and18late full reference YUV/raw selected PPC endpoints pass.',
    'These ordinary fixtures do not directly exercise periodic VI due while busy; dedicated actual timer latch fixture still required.',
    'No asynchronous physical Wii/live performance/visual/audio/profile/save/controller proof or default promotion.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
