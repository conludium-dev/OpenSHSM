"""Reuse packet/audio/capture audit with strict explicit temporary evidence paths for exact-index candidate."""
from pathlib import Path
import argparse
import hashlib
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', type=Path, required=True)
args = parser.parse_args()
artifacts = args.artifacts.resolve()
assert artifacts.parent == Path('/private/tmp')
assert re.fullmatch(r'openshsm-run-[A-Za-z0-9_-]+', artifacts.name)
run_path = artifacts / 'headless-sc-pc-headless-windowed-dispatch-o2-result.json'
run = json.loads(run_path.read_text())
assert run['temporaryEvidence'] and Path(run['artifactDirectory']).resolve() == artifacts
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-dispatch-o2'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base = Path('experiments/wii-static-recomp/audit_stock_scheduler_o2.py')
script = base.read_text()
patches = [
    ("output = root / 'window-scheduler-o2'", "output = root / 'window-dispatch-o2'"),
    ("parent_path = root / 'window-movie-late/build.json'", "parent_path = root / 'window-scheduler-o2/build.json'"),
    ('SCHEDULER_O2_CONTRACT_CALLBACK4_SDK7_SC3_LATE18_EQUAL', 'DISPATCH_O2_ROUTES_CALLBACK4_SDK7_SC3_LATE18_EQUAL'),
    ('headless-sc-pc-headless-windowed-scheduler-o2', 'headless-sc-pc-headless-windowed-dispatch-o2'),
    ('headless-sc-pc-scheduler-o2-movie-timing.jsonl', 'headless-sc-pc-dispatch-o2-movie-timing.jsonl'),
    ('headless-sc-pc-scheduler-o2-efb', 'headless-sc-pc-dispatch-o2-efb'),
    ("prior_path = root / 'window-movie-late/live-input-audit.json'", "prior_path = root / 'window-scheduler-o2/live-input-audit.json'"),
    ("prior['result'] == 'DELAYED_LIVE_OWNED_MOVIE_PACKETS_AUDITED'", "prior['result'] == 'SCHEDULER_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED'"),
    ('SCHEDULER_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED', 'DISPATCH_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED')]
for before, after in patches:
    assert before in script
    script = script.replace(before, after)
# The comparison input keeps its original scheduler result.
script = script.replace("prior['result'] == 'DISPATCH_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED'",
    "prior['result'] == 'SCHEDULER_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED'")
script = script.replace("scope = {'__file__': __file__}",
    '''script = script.replace("root / 'headless-sc-pc-", "artifacts / 'headless-sc-pc-")
scope = {'__file__': __file__, 'artifacts': artifacts}''')
script = script.replace("text = (root / 'headless-sc-pc-", "text = (artifacts / 'headless-sc-pc-")
exec(compile(script, str(base), 'exec'), {'__file__': __file__, 'artifacts': artifacts})
report_path = output / 'live-input-audit.json'
report = json.loads(report_path.read_text())
report.update(artifactDirectory=str(artifacts), baseDispatchAuditorSha256=sha(base))
report['limits'].append('Explicit temporary evidence path validated; logs/timing/packets/run result may expire, hashes and paths retained.')
report_path.write_text(json.dumps(report, indent=2) + '\n')
