"""Verify pure predicate restoration plus actual masked/due/native DEC and existing runtime/frame endpoints."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-dec-ee-gate'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
before, after = build['patch']
source = Path(build['sourcePath']).read_text()
assert source.count(after) == 1
assert source.replace(after, before, 1) == Path(build['originalSourcePath']).read_text()
assert source.index('EventScheduler::get().advance(ctx, ctx.read_timebase());') < source.index(after)
assert build['arguments'] == json.loads((root / 'window-ios-o2/build.json').read_text())['arguments']
base = Path('experiments/wii-static-recomp/verify_stock_scheduler_o2.py')
script = base.read_text()
patches = [
    ("output = root / 'window-scheduler-o2'", "output = root / 'window-dec-ee-gate'"),
    ("parent_path = root / 'window-movie-late/build.json'", "parent_path = root / 'window-dispatch-o2/build.json'"),
    ("assert Path(build['sourcePath']).read_bytes() == Path(build['originalSourcePath']).read_bytes()", "assert Path(build['sourcePath']).read_text().replace(build['patch'][1], build['patch'][0], 1) == Path(build['originalSourcePath']).read_text()"),
    ("assert build['arguments'] == build['originalArguments'] + ['-O2']", "assert build['arguments'] == json.loads((root / 'window-ios-o2/build.json').read_text())['arguments']"),
    ("member != 'event_scheduler.cpp.o'", "member != 'ios.cpp.o'"),
    ("flags = parent['changes']['37']['arguments']", "flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']['37']['arguments']"),
    ("('callback', public / 'stock_callback_runtime_probe.cpp', 'ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4'),",
     "('callback', public / 'stock_callback_runtime_probe.cpp', 'ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4'),\n    ('dec', public / 'stock_dec_ee_gate_probe.cpp', 'DEC_EE_MASK_DUE_HANDLER_NONLOCAL_ENDPOINT_PASS9'),"),
    ("name == 'callback'", "name in ('callback', 'dec')"),
    ("assert prior['buildSha256'] == sha(parent_path)", "assert prior['buildSha256'] == sha(root / 'window-movie-late/build.json')"),
    ('SCHEDULER_O2_CONTRACT_CALLBACK4_SDK7_SC3_LATE18_EQUAL', 'DEC_EE_GATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL')]
for old, new in patches:
    assert old in script
    script = script.replace(old, new)
start = script.index("command = list(prior['linkCommand'])")
end = script.index("exe = temporary / 'frame'", start)
script = script[:start] + """command = list(build['linkCommand'])
fixture = Path(prior['linkCommand'][1])
assert sha(fixture) == prior['objectSha256']
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(fixture))
""" + script[end:]
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
report.update(baseVerifierSha256=sha(base))
report['limits'] = ['Only DEC predicate order in native IOS, same source/flags restored; unconditional preceding event advance preserved.',
    'Actual native DEC9 modes cover masked due/notdue, enabled due/notdue, valid guest-context handler nonlocal dispatch, missing/invalid handler, blocked callback.',
    'Selected PPC/pending/guest saved-context memory endpoints identical baseline/candidate; masked remains armed.',
    'Existing scheduler/IOS callback4/SDK7/emittedSC3 and18late whole YUV/raw PPC reference endpoints exact.',
    'Deterministic instruction-clock fixtures, not full asynchronous Wii hardware IRQ/device/live timing acceptance; no default promotion.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
print('DEC_EE_GATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL')
