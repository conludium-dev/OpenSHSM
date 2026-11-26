"""Verify delayed diagnostics retain exact original packet and whole-frame/state endpoints."""
from pathlib import Path
import hashlib
import json

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-movie-late'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
assert build['gateProbe']['result'] == 'MOVIE_CAPTURE_DELAY_BOUNDARY_INVALID_CLOCK_PASS'
assert sha(Path(build['gateProbe']['executablePath'])) == build['gateProbe']['executableSha256']
assert build['parentBuildSha256'] == sha(root / 'window-texture-o2/build.json')
base = Path('experiments/wii-static-recomp/verify_stock_movie_input_frame.py')
script = base.read_text()
patches = [
    ("output = root / 'window-movie-input'", "output = root / 'window-movie-late'"),
    ("restored == (root / 'window-cpu-time/stock_movie_timing.h').read_text()", "restored == Path(build['headerOriginalPath']).read_text()"),
    ("env['NWII_MOVIE_TIMING'] = str(timing)", "env['NWII_MOVIE_TIMING'] = str(timing)\n    env['NWII_MOVIE_CAPTURE_AFTER_MS'] = ['0', '180000', 'invalid'][iteration]"),
    ("assert [row['site'] for row in events] == [0x80209D80, 0x8020A044]", "assert [row['site'] for row in events] == ([0x80209D80, 0x8020A044] if iteration == 0 else [])"),
    ("'wallUs': events[1]['hostUs'] - events[0]['hostUs']", "'mode': env['NWII_MOVIE_CAPTURE_AFTER_MS'], 'observedEvents': len(events),\n        'wallUs': events[1]['hostUs'] - events[0]['hostUs'] if events else None"),
    ("'ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3'", "'MOVIE_LATE_GATE_PACKET_FRAME_STATE_IDENTICAL3'")]
for before, after in patches:
    expected = 2 if before == "'ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3'" else 1
    assert script.count(before) == expected
    script = script.replace(before, after)
exec(compile(script, str(base), 'exec'), {'__file__': __file__})
report_path = output / 'component-verification.json'
report = json.loads(report_path.read_text())
report.update(baseVerifierSha256=sha(base), gateProbe=build['gateProbe'])
report['limits'].extend(['Zero delay emits original decoder pair; delayed and invalid modes emit no timing events in short fixture.',
    'All three modes still produce exact original packet, full reference YUV and selected PPC state.',
    'Manual packet hook in fixture independent of delayed timing; late live caller/70s boundary/full runtime not yet verified.'])
report_path.write_text(json.dumps(report, indent=2) + '\n')
print('MOVIE_LATE_GATE_PACKET_FRAME_STATE_IDENTICAL3')
