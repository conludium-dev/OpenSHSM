"""Retain existing safe delivery, but latch recurring VI while dispatch context is busy."""
from pathlib import Path
import hashlib
import json

base = Path('experiments/wii-static-recomp/build_stock_dec_ee_gate.py')
script = base.read_text()
before = '''!(nwii::runtime::hw::pi_intsr & 0x100) &&
                      (c.dispatch_saved_ctx == 0 || c.mmu.read32(0x800000E4) == 0)'''
after = '!(nwii::runtime::hw::pi_intsr & 0x100)'
start = script.index("before = 'if (ctx.dec_expired()")
end = script.index('text = original.read_text()', start)
script = script[:start] + f'before = {before!r}\nafter = {after!r}\n' + script[end:]
patches = [
    ("output = root / 'window-dec-ee-gate'", "output = root / 'window-vi-busy-latch'"),
    ("parent_path = root / 'window-dispatch-o2/build.json'", "parent_path = root / 'window-current-vi-timer/build.json'"),
    ('DISPATCH_O2_ROUTES_CALLBACK4_SDK7_SC3_LATE18_EQUAL', 'CURRENT_TIMER_MAIN_ONLY_LINK_SOURCE_SDK_MARKERS_VERIFIED'),
    ("ios_path = root / 'window-ios-o2/build.json'", "ios_path = root / 'window-dec-ee-gate/build.json'"),
    ("original = root / 'window-ios-o2/ios.cpp'", "original = Path(ios['sourcePath'])"),
    ("assert text.index('EventScheduler::get().advance(ctx, ctx.read_timebase());') < text.index(before)",
     "assert 'if (use_new_path && (handler_in_flight || (!idle && sched_disabled))) {' in text"),
    ('openshsm-dec-ee-gate-', 'openshsm-vi-busy-latch-'),
    ('OpenSHSMStockDECEEGate', 'OpenSHSMStockVIBusyLatch'),
    ('PURE_DEC_DEADLINE_EE_GATE_BUILT_UNVERIFIED', 'EXISTING_VI_BUSY_LATCH_BUILT_UNVERIFIED')]
for old, new in patches:
    assert old in script
    script = script.replace(old, new)
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = Path('work/private-game/static-recomp/stock-baseline/window-vi-busy-latch/build.json')
report = json.loads(report_path.read_text())
proof = report_path.parent.parent / 'vi-pending-proof/verification.json'
assert json.loads(proof.read_text())['result'] == 'CURRENT_VI_TEXT_REPRODUCED_PENDING_DEFERRED_DELIVERY_PASS3'
report['pendingProofSha256'] = hashlib.sha256(proof.read_bytes()).hexdigest()
report['baseBuilderSha256'] = hashlib.sha256(base.read_bytes()).hexdigest()
report['limits'] = [
    'Only recurring VI busy predicate removed, retaining mask/in_callback/already pending gates.',
    'Existing IOS EE/busy safe-delivery guard, event queue, period/timebase/DEC/audio remain unchanged.',
    'Native PC adaptation supported by actual pending-delivery tests, not exact physical Wii behavior proof.',
    'No second queue/producer/catch-up; native and live cadence/frame/audio/visual verification pending, not promoted.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
