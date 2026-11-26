"""Audit the profiled run into its immutable private artifact directory."""
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
parser.add_argument('--sample-symbols', action='store_true')
args = parser.parse_args()
artifacts = args.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp') and artifacts.name.startswith('openshsm-run-')
base = Path(__file__).resolve().parent / 'audit_stock_movie_input.py'
script = base.read_text()
unit_block = '''for unit, change in build['changes'].items():
    assert (output / f'output_{unit}.cpp').read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(output / f'output_{unit}.cpp.o') == change['objectSha256']
'''
patches = [
    ("output = root / 'window-movie-input'", "output = root / 'window-post-present'"),
    (unit_block, ''),
    ("'ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3'", "'POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED'"),
    ("cap['buildSha256'] == sha(build_path)", "cap['buildSha256'] == sha(root / 'window-movie-input/build.json')"),
    ("sha(output / 'OpenSHSMStockMovieInput')", "sha(Path(build['executablePath']))"),
    ("root / 'headless-sc-pc-headless-windowed-movie-input-result.json'", "artifacts / 'headless-sc-pc-headless-windowed-post-present-profile-result.json'"),
    ("root / 'headless-sc-pc-headless-windowed-movie-input.log'", "artifacts / 'headless-sc-pc-headless-windowed-post-present-profile.log'"),
    ("root / 'headless-sc-pc-movie-input-movie-timing.jsonl'", "artifacts / 'headless-sc-pc-post-present-profile-movie-timing.jsonl'"),
    ("output / 'live-input-audit.json'", "artifacts / 'profile-input-audit.json'")]
for before, after in patches:
    assert script.count(before) == 1, before
    script = script.replace(before, after, 1)
if args.sample_symbols:
    script = script.replace("output = root / 'window-post-present'", "output = root / 'window-sample-symbols'")
    script = script.replace('POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED',
        'SAMPLE_SYMBOLS_SECTIONS_SIGNATURE_VERIFIED_FOR_PROFILING_ONLY')
exec(compile(script, str(base), 'exec'), {'__file__': str(Path(__file__).resolve()), 'artifacts': artifacts})
