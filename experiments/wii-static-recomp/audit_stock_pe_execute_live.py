"""Audit ordered-execution live movie cadence and late texture coherence evidence."""
from pathlib import Path
import json

base = Path('experiments/wii-static-recomp/audit_stock_texture_late.py')
script = base.read_text().replace('window-texture-late', 'window-pe-execute')
script = script.replace('texture-late', 'pe-execute')
script = script.replace('window-dispatch-select/build.json', 'window-texture-late/build.json')
script = script.replace('TEXTURE_LATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL',
    'PE_EXECUTE_GL172_EVICTION1600_GPU6_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED')
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
report_path = scope['path']
report = json.loads(report_path.read_text())
baseline_path = Path('/private/tmp/openshsm-run-nbabr6mn/texture-coherence-audit.json')
baseline = json.loads(baseline_path.read_text())
report.update(result='PE_ORDERED_EXECUTION_LIVE_MOVIE_TEXTURE_COHERENCE_AUDITED',
    baseAuditorSha256=scope['sha'](base), priorCoherenceSha256=scope['sha'](baseline_path),
    priorCoherenceSummary={key: baseline[key] for key in ['captures', 'pairedCaptures', 'changedPairs', 'decodedMixedPairs']})
report['limits'].append('GX counter now includes completion batches, not unique displayed video FPS; no headline improvement from this count.')
report['limits'].append('Prior coherence run had no movie capture; separate paired-texture contexts are not controlled same-frame causality proof.')
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({key: report[key] for key in ['captures', 'pairedCaptures', 'changedPairs', 'decodedMixedPairs', 'priorCoherenceSummary', 'movieEvidenceMissing']}, indent=2))
