"""Audit owned movie cadence/coherence after removing rejected observer calls."""
from pathlib import Path
import json

base = Path('experiments/wii-static-recomp/audit_stock_texture_late.py')
script = base.read_text().replace('window-texture-late', 'window-context-stage')
script = script.replace('texture-late', 'context-stage-live')
script = script.replace('window-dispatch-select/build.json', 'window-post-present/build.json')
script = script.replace('TEXTURE_LATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL',
    'CONTEXT_STAGE_CACHE234_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED')
scope = {'__file__': __file__}
exec(compile(script, str(base), 'exec'), scope)
path = scope['path']
report = json.loads(path.read_text())
report.update(result='CONTEXT_STAGE_LIVE_OWNED_MOVIE_AUDIO_COHERENCE_AUDITED',
    baseAuditorSha256=scope['sha'](base))
report['limits'].append('Only four always-rejected diagnostic calls omitted; no loop/clock/IRQ/cache or decoder replacement.')
report['limits'].append('Separate live sessions and recorder IO are not a controlled hardware performance experiment.')
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
print(json.dumps({key: report[key] for key in ['captures', 'pairedCaptures', 'changedPairs', 'decodedMixedPairs', 'movieEvidenceMissing']}, indent=2))
