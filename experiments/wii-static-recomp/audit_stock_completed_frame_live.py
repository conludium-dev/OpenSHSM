"""Reuse owned packet/phase/texture audit for the completed-frame experiment."""
from pathlib import Path
import json

base = Path('experiments/wii-static-recomp/audit_stock_texture_late.py')
script = base.read_text().replace('window-texture-late', 'window-completed-frame')
script = script.replace('texture-late', 'completed-frame-live')
script = script.replace('window-dispatch-select/build.json', 'window-pe-execute/build.json')
script = script.replace('TEXTURE_LATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL',
    'COMPLETED_FRAME_GL172_EVICTION1600_GPU16_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED')
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
report_path = scope['path']
report = json.loads(report_path.read_text())
report.update(result='COMPLETED_FRAME_LIVE_MOVIE_TEXTURE_COHERENCE_AUDITED',
    baseAuditorSha256=scope['sha'](base))
report['limits'].append('GX counts copy-bearing batches only; presentation screenshot indices no longer correspond to old host-loop indices.')
report['limits'].append('No controlled same-frame title comparison or visual promotion from numerical audit alone.')
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({key: report[key] for key in ['captures', 'pairedCaptures', 'changedPairs', 'decodedMixedPairs', 'movieEvidenceMissing']}, indent=2))
