"""Run existing actual CPU/callback/DEC/SDK/SC/late-frame/timer gates on output38 delta."""
from pathlib import Path
import argparse
import hashlib
import json

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--cache-proof', type=Path, required=True)
args = parser.parse_args()
build_path = args.build.resolve()
output = build_path.parent
build = json.loads(build_path.read_text())
cache_path = args.cache_proof.resolve()
cache_proof = json.loads(cache_path.read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert cache_proof['result'] == 'CONTEXT_STAGE_GATE_CACHE234_ENABLED_DISABLED_PARENT_ENDPOINTS_EQUAL'
assert cache_proof['buildSha256'] == sha(build_path)
for path, digest in cache_proof['dependencies'].items():
    assert sha(path) == digest
public = Path(__file__).resolve().parent
base = public / 'verify_stock_scheduler_o2.py'
script = base.read_text()
start = script.index('assert sha(parent_path)')
end = script.index('temporary = Path(tempfile.mkdtemp', start)
script = script[:start] + script[end:]
patches = [("output = root / 'window-scheduler-o2'", f'output = Path({str(output)!r})'),
    ("parent_path = root / 'window-movie-late/build.json'", "parent_path = root / 'window-post-present/build.json'"),
    ("flags = parent['changes']['37']['arguments']", "flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']['37']['arguments']"),
    ("('callback', public / 'stock_callback_runtime_probe.cpp', 'ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4'),",
        "('callback', public / 'stock_callback_runtime_probe.cpp', 'ACTUAL_CALLBACK_QUEUE_NONLOCAL_ENDPOINT_PASS4'),\n"
        "    ('dec', public / 'stock_dec_ee_gate_probe.cpp', 'DEC_EE_MASK_DUE_HANDLER_NONLOCAL_ENDPOINT_PASS9'),"),
    ("assert prior['buildSha256'] == sha(parent_path)", "assert prior['buildSha256'] == sha(root / 'window-movie-late/build.json')")]
for before, after in patches:
    assert script.count(before) == 1
    script = script.replace(before, after, 1)
assert script.count("name == 'callback'") == 2
script = script.replace("name == 'callback'", "name in ('callback', 'dec')")
start = script.index("command = list(prior['linkCommand'])")
end = script.index("exe = temporary / 'frame'", start)
script = script[:start] + """command = list(build['linkCommand'])
fixture = Path(prior['linkCommand'][1])
assert sha(fixture) == prior['objectSha256']
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(fixture))
""" + script[end:]
exec(compile(script, str(base), 'exec'), {'__file__': str(Path(__file__).resolve())})
timer_base = public / 'verify_stock_vi_timer_latch.py'
script = timer_base.read_text()
before = "output = root / 'window-vi-busy-latch'"
assert script.count(before) == 1
script = script.replace(before, f'output = Path({str(output)!r})', 1)
exec(compile(script, str(timer_base), 'exec'), {'__file__': str(Path(__file__).resolve())})
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
report.update(result='CONTEXT_STAGE_CACHE234_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED',
    cacheProofPath=str(cache_path), cacheProofSha256=sha(cache_path),
    reusedVerifierSha256={str(path): sha(path) for path in [base, timer_base]},
    timerProofSha256=sha(output / 'timer-latch-verification.json'))
report['limits'] = ['Only four always-rejected native observer calls omitted in unit38; common observer definitions and original PPC/SC/cache/callback/clock operations retained.',
    'Actual cache234 cases in enabled/disabled modes, scheduler/callback4/DEC9/SDK7/SC3/late18/timer3 endpoints verified.',
    'Isolated fixtures, not live original IRQ producer/Wii cache semantics/full-game visual/audio/performance acceptance.',
    'No default/promotion or measured FPS gain yet.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], report_path)
