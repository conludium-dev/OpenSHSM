"""Verify current optimized profiling wrapper, retained runtime and enabled nonlocal/frame contracts."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-callback-o2-profile'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
parent_path = root / 'window-dispatch-o2/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
prepared_path = root / 'callback-profile-component/verification.json'
assert sha(prepared_path) == build['preparedComponentSha256']
prepared = json.loads(prepared_path.read_text())
ios = Path(build['iosSourcePath']).read_text()
assert sha(Path(build['iosSourcePath'])) == build['iosSourceSha256']
ios = ios.replace('#include "stock_callback_profile.h"\n', '', 1)
assert ios.count(prepared['wrapper']) == 1
ios = ios.replace(prepared['wrapper'], '', 1)
for before, after in reversed(prepared['patches']):
    assert ios.count(after) == 1
    ios = ios.replace(after, before, 1)
assert ios == Path(build['iosOriginalPath']).read_text()
assert build['iosArguments'] == json.loads((root / 'window-ios-o2/build.json').read_text())['arguments']
header = Path(build['headerPath']).read_text()
for before, after in reversed(build['headerPatches']):
    assert header.count(after) == 1
    header = header.replace(after, before, 1)
assert header == Path(build['headerOriginalPath']).read_text()
expected = list(parent['linkCommand'])
archive = Path(build['archivePath'])
old_archive = next(Path(arg) for arg in expected if Path(arg).name == 'libnwiiruntime.a')
expected[expected.index(str(old_archive))] = str(archive)
for unit, change in build['changes'].items():
    old = next(arg for arg in expected if Path(arg).name == f'output_{unit}.cpp.o')
    expected[expected.index(old)] = change['objectPath']
    assert Path(change['sourcePath']).read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(Path(change['objectPath'])) == change['objectSha256']
expected[expected.index('-o') + 1] = build['executablePath']
assert expected == build['linkCommand']
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
assert sha(archive) == build['archiveSha256']
for member, digest in build['members'].items():
    actual = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert hashlib.sha256(actual).hexdigest() == digest
    if member != 'ios.cpp.o':
        assert actual == subprocess.check_output(['/usr/bin/ar', '-p', str(old_archive), member])
base = Path('experiments/wii-static-recomp/verify_stock_scheduler_o2.py')
script = base.read_text()
start = script.index("assert Path(build['sourcePath'])")
end = script.index('temporary = Path(tempfile.mkdtemp', start)
script = script[:start] + script[end:]
start = script.index("command = list(prior['linkCommand'])")
end = script.index("exe = temporary / 'frame'", start)
script = script[:start] + '''command = list(build['linkCommand'])
fixture = Path(prior['linkCommand'][1])
assert sha(fixture) == prior['objectSha256']
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(fixture))
''' + script[end:]
patches = [
    ("output = root / 'window-scheduler-o2'", "output = root / 'window-callback-o2-profile'"),
    ("parent_path = root / 'window-movie-late/build.json'", "parent_path = root / 'window-dispatch-o2/build.json'"),
    ("flags = parent['changes']['37']['arguments']", "flags = build['changes']['37']['arguments']"),
    ("assert prior['buildSha256'] == sha(parent_path)", "assert prior['buildSha256'] == sha(root / 'window-movie-late/build.json')"),
    ("env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}",
     "env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}\nenv['NWII_MOVIE_TIMING'] = str(temporary / 'enabled')"),
    ("selected = dict(env)", "selected = dict(env)\n            selected['NWII_MOVIE_TIMING'] = str(raw) + '.timing'"),
    ("frames.append({'movie':", '''events = [json.loads(line) for line in Path(str(raw) + '.timing').read_text().splitlines()]
            assert len(events) == 2 and [event['site'] for event in events] == [0x80209D80, 0x8020A044]
            before, after = events[0]['callbackProfile'], events[1]['callbackProfile']
            assert len(before) == len(after) == 10 and all(a <= b for a, b in zip(before, after))
            assert after[0] > before[0] and after[8] == 0
            frames.append({'callbackDelta': [b - a for a, b in zip(before, after)], 'movie':'''),
    ('SCHEDULER_O2_CONTRACT_CALLBACK4_SDK7_SC3_LATE18_EQUAL', 'CURRENT_CALLBACK_O2_PROFILE_NONLOCAL4_SDK7_SC3_LATE18_EQUAL')]
for before, after in patches:
    assert before in script
    script = script.replace(before, after)
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
report.update(baseVerifierSha256=sha(base))
report['limits'] = ['Current original IOS body restored byte-for-byte, SAME current O2 arguments; only existing trivial counters/wrapper added.',
    'Header restoration equals current delayed observer; same guest sources/master/runtime/IRQ/waits otherwise retained.',
    'Enabled native scheduler/IOS nonlocal4/SDK7/emittedSC3 endpoints equal;18 late reference YUV/raw PPC endpoints exact and counter deltas valid.',
    'Sampling/clock/wrapper overhead changes performance; missing ordinary returns not exact IRQ count or timed as zero.',
    'Isolated fixtures not complete live IRQ/visual/audio/profile/story/controller/hardware proof; live profiling pending.']
report_path.write_text(json.dumps(report, indent=2) + '\n')
print('CURRENT_CALLBACK_O2_PROFILE_NONLOCAL4_SDK7_SC3_LATE18_EQUAL')
