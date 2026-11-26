"""Audit exact late live packet/capture/audio changes for the one-predicate DEC gate candidate."""
from pathlib import Path
import hashlib
import json

base = Path('experiments/wii-static-recomp/audit_stock_dispatch_o2.py')
script = base.read_text()
patches = [
    ('headless-sc-pc-headless-windowed-dispatch-o2', 'headless-sc-pc-headless-windowed-dec-ee-gate'),
    ('headless-sc-pc-dispatch-o2-movie-timing.jsonl', 'headless-sc-pc-dec-ee-gate-movie-timing.jsonl'),
    ('headless-sc-pc-dispatch-o2-efb', 'headless-sc-pc-dec-ee-gate-efb'),
    ("output = root / 'window-dispatch-o2'", "output = root / 'window-dec-ee-gate'"),
    ("parent_path = root / 'window-scheduler-o2/build.json'", "parent_path = root / 'window-dispatch-o2/build.json'"),
    ('DISPATCH_O2_ROUTES_CALLBACK4_SDK7_SC3_LATE18_EQUAL', 'DEC_EE_GATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL'),
    ("prior_path = root / 'window-scheduler-o2/live-input-audit.json'", "prior_path = root / 'window-dispatch-o2/live-input-audit.json'"),
    ("prior['result'] == 'SCHEDULER_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED'", "prior['result'] == 'DISPATCH_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED'"),
    ('DISPATCH_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED', 'DEC_EE_GATE_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED')]
for before, after in patches:
    assert before in script
    script = script.replace(before, after)
script = script.replace("prior['result'] == 'DEC_EE_GATE_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED'",
    "prior['result'] == 'DISPATCH_O2_LATE_LIVE_PACKET_VISUAL_AUDIO_AUDITED'")
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-dec-ee-gate'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report_path = output / 'live-input-audit.json'
report = json.loads(report_path.read_text())
report.update(baseDecAuditorSha256=sha(base))
report['limits'].append('Only pure DEC check under masked EE skipped; earlier event queue advance/audio deadlines and allowed IRQ policy retained.')
report_path.write_text(json.dumps(report, indent=2) + '\n')
