"""Check helper-only link delta and actual native runtime/late/timer endpoints."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-dispatch-select'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
parent_path = root / 'window-vi-busy-latch/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
before, after = build['abiRename']
assert Path(build['sourcePath']).read_text().replace(after, before, 1) == Path(build['originalSourcePath']).read_text()
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
assert sha(Path(build['objectPath'])) == build['objectSha256']
assert sha(Path(build['executablePath'])) == build['executableSha256']
expected = list(parent['linkCommand'])
expected[expected.index(build['originalObjectPath'])] = build['objectPath']
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
base = Path('experiments/wii-static-recomp/verify_stock_scheduler_o2.py')
script = base.read_text()
start = script.index('assert sha(parent_path)')
end = script.index('temporary = Path(tempfile.mkdtemp', start)
script = script[:start] + script[end:]
patches = [
    ("output = root / 'window-scheduler-o2'", "output = root / 'window-dispatch-select'"),
    ("parent_path = root / 'window-movie-late/build.json'", "parent_path = root / 'window-vi-busy-latch/build.json'"),
    ("flags = parent['changes']['37']['arguments']", "flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']['37']['arguments']"),
    ("('callback', public / 'stock_callback_runtime_probe.cpp', 'ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4'),",
     "('callback', public / 'stock_callback_runtime_probe.cpp', 'ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4'),\n    ('dec', public / 'stock_dec_ee_gate_probe.cpp', 'DEC_EE_MASK_DUE_HANDLER_NONLOCAL_ENDPOINT_PASS9'),"),
    ("name == 'callback'", "name in ('callback', 'dec')"),
    ("assert prior['buildSha256'] == sha(parent_path)", "assert prior['buildSha256'] == sha(root / 'window-movie-late/build.json')"),
    ('SCHEDULER_O2_CONTRACT_CALLBACK4_SDK7_SC3_LATE18_EQUAL', 'DISPATCH_SELECT_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL')]
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
timer_base = Path('experiments/wii-static-recomp/verify_stock_vi_timer_latch.py')
timer_script = timer_base.read_text().replace("output = root / 'window-vi-busy-latch'", "output = root / 'window-dispatch-select'")
exec(compile(timer_script, str(timer_base), 'exec'), {'__file__': __file__})
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
report.update(result='DISPATCH_SELECT_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL',
    baseVerifierSha256=sha(base), timerVerifierSha256=sha(timer_base),
    timerProofSha256=sha(output / 'timer-latch-verification.json'))
report['limits'] = ['Only pure exact-index helper replaced; source ABI rename restored/allother link inputs exact.',
    'Actual scheduler/callback4/DEC9/SDK7/SC3/18late full reference YUV/raw PPC equal; periodic VI latch/defer/coalesce/deliver3 passes.',
    'No original hardware/asynchronous IRQ/live performance/visual/audio/profile/controller acceptance or promotion.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
